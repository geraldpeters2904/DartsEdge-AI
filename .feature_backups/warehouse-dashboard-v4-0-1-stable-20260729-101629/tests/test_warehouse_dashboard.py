import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_db
from app.main import app
from app.services.warehouse_dashboard_service import (
    WarehouseDashboardService,
)
from tests.helpers.database import create_test_session


class WarehouseDashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = WarehouseDashboardService()

    def tearDown(self):
        self.db.close()

    def test_build_returns_metrics_without_known_tables(self):
        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(
                self.db,
                capture_root=root,
            )

        keys = {metric.key for metric in dashboard.metrics}
        self.assertIn("players", keys)
        self.assertIn("fixtures", keys)
        self.assertIn("captured", keys)

    def test_counts_recognised_players_and_fixtures_tables(self):
        self.db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS fixtures "
                "(id INTEGER PRIMARY KEY, status TEXT)"
            )
        )
        self.db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS players "
                "(id INTEGER PRIMARY KEY)"
            )
        )
        self.db.execute(
            text(
                "INSERT INTO fixtures (status) VALUES "
                "('scheduled'), ('completed')"
            )
        )
        self.db.execute(
            text("INSERT INTO players DEFAULT VALUES")
        )
        self.db.commit()

        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(
                self.db,
                capture_root=root,
            )

        self.assertEqual(dashboard.table_counts["players"], 1)
        self.assertEqual(dashboard.table_counts["fixtures"], 2)
        metrics = {metric.key: metric.value for metric in dashboard.metrics}
        self.assertEqual(metrics["scheduled"], 1)
        self.assertEqual(metrics["completed"], 1)

    def test_capture_summary_is_included(self):
        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(
                self.db,
                capture_root=root,
            )

        self.assertEqual(dashboard.capture_summary["sessions"], 0)
        self.assertEqual(dashboard.capture_summary["missing_matches"], 0)


class WarehouseDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_page_returns_200(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/warehouse-dashboard",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Warehouse Dashboard", response.text)
        self.assertIn("Warehouse Health", response.text)
        self.assertIn("Capture Progress", response.text)


if __name__ == "__main__":
    unittest.main()
