import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.historical_import import (
    HistoricalImportBatch,
)
from tests.helpers.database import create_test_session


class CollectorRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_collector_page_returns_200(self):
        response = self.client.get("/admin/collector")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Data Collection Centre",
            response.text,
        )
        self.assertIn(
            "Prepare an import",
            response.text,
        )

    def test_collector_page_contains_all_upload_controls(self):
        response = self.client.get("/admin/collector")

        self.assertIn(
            'name="fixtures_file"',
            response.text,
        )
        self.assertIn(
            'name="results_file"',
            response.text,
        )
        self.assertIn(
            'name="statistics_file"',
            response.text,
        )
        self.assertIn(
            'name="odds_file"',
            response.text,
        )

    def test_collector_page_contains_provider_and_competition(self):
        response = self.client.get("/admin/collector")

        self.assertIn(
            'name="provider"',
            response.text,
        )
        self.assertIn(
            'name="competition"',
            response.text,
        )
        self.assertIn(
            "MODUS Super Series",
            response.text,
        )

    def test_collector_page_displays_recent_batches(self):
        batch = HistoricalImportBatch(
            batch_uuid=(
                "12345678-1234-1234-1234-123456789012"
            ),
            filename="fixtures.csv",
            provider="manual-research",
            competition_code="MODUS",
            status="imported",
            received_rows=12,
            created_matches=6,
            duplicate_matches=1,
            rejected_rows=0,
            created_players=4,
        )

        self.db.add(batch)
        self.db.commit()

        response = self.client.get("/admin/collector")

        self.assertEqual(response.status_code, 200)
        self.assertIn("12345678", response.text)
        self.assertIn("fixtures.csv", response.text)
        self.assertIn("manual-research", response.text)
        self.assertIn("imported", response.text)

    def test_collector_stylesheet_is_available(self):
        response = self.client.get(
            "/static/css/collector.css"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            ".collector-shell",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
