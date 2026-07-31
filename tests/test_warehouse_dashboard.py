import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_db
from app.main import app
from app.services.warehouse_dashboard_service import WarehouseDashboardService
from tests.helpers.database import create_test_session


class WarehouseDashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = WarehouseDashboardService()

    def tearDown(self):
        self.db.close()

    def test_build_returns_core_metrics(self):
        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(self.db, capture_root=root)

        keys = {metric.key for metric in dashboard.metrics}
        self.assertTrue(
            {"players", "fixtures", "matches", "statistics", "captured"}
            .issubset(keys)
        )

    def test_current_matches_table_is_used_for_fixture_lifecycle(self):
        self.db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS matches "
                "(id INTEGER PRIMARY KEY, status TEXT)"
            )
        )
        self.db.execute(
            text(
                "INSERT INTO matches (status) VALUES "
                "('scheduled'), ('completed')"
            )
        )
        self.db.commit()

        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(self.db, capture_root=root)

        metrics = {metric.key: metric.value for metric in dashboard.metrics}
        self.assertEqual(dashboard.table_counts["fixtures"], 2)
        self.assertEqual(dashboard.table_counts["matches"], 2)
        self.assertEqual(metrics["scheduled"], 1)
        self.assertEqual(metrics["completed"], 1)

    def test_current_statistics_table_is_recognised(self):
        self.db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS match_player_stats "
                "(id INTEGER PRIMARY KEY)"
            )
        )
        self.db.execute(
            text("INSERT INTO match_player_stats DEFAULT VALUES")
        )
        self.db.commit()

        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(self.db, capture_root=root)

        self.assertEqual(dashboard.table_counts["statistics"], 1)

    def test_current_import_preview_table_is_recognised(self):
        self.db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS historical_import_previews ("
                "id INTEGER PRIMARY KEY, "
                "preview_uuid TEXT, "
                "provider TEXT, "
                "competition_code TEXT, "
                "status TEXT, "
                "created_at TEXT)"
            )
        )
        self.db.execute(
            text(
                "INSERT INTO historical_import_previews "
                "(preview_uuid, filename, provider, competition_code, status, "
                "rows_json, report_json, created_at) "
                "VALUES ('preview-1', 'fixtures.csv', 'modus-official', "
                "'MODUS', 'pending', '[]', '{}', "
                "'2026-07-29 10:00:00')"
            )
        )
        self.db.commit()

        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(self.db, capture_root=root)

        self.assertEqual(len(dashboard.recent_imports), 1)
        self.assertEqual(
            dashboard.recent_imports[0].identifier,
            "preview-1",
        )

    def test_capture_summary_is_included(self):
        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(self.db, capture_root=root)

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

    def test_page_returns_200_and_renders_stable_sections(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/warehouse-dashboard",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-testid="warehouse-metrics"', response.text)
        self.assertIn('data-testid="warehouse-health"', response.text)
        self.assertIn('data-testid="capture-progress"', response.text)
        self.assertIn('data-testid="recent-activity"', response.text)
        self.assertIn('data-testid="database-storage"', response.text)

    def test_page_renders_core_metric_labels(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/warehouse-dashboard",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        for label in (
            "Players",
            "Fixtures",
            "Matches",
            "Statistics",
            "Scheduled",
            "Completed",
        ):
            self.assertIn(label, response.text)


if __name__ == "__main__":
    unittest.main()
