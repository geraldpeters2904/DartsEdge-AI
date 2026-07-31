import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchService,
)
from tests.helpers.database import create_test_session


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalOperationsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_page_returns_200_without_batch(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/historical-operations",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Historical Operations Centre",
            response.text,
        )
        self.assertIn(
            "Build a historical capture batch.",
            response.text,
        )
        self.assertIn(
            "Warehouse readiness",
            response.text,
        )

    def test_page_shows_current_batch_group(self):
        with tempfile.TemporaryDirectory() as root:
            HistoricalCaptureBatchService().create(
                root=root,
                results_pages=[
                    (
                        "series14-week01-group-a.html",
                        self.results_html,
                    )
                ],
            )

            response = self.client.get(
                "/admin/historical-operations",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Series 14", response.text)
        self.assertIn("Week 1", response.text)
        self.assertIn("Group A", response.text)
        self.assertIn("Open Current Group", response.text)

        # Functional heading used by the rendered template.
        self.assertIn(
            "Historical import status",
            response.text,
        )
        self.assertIn(
            "Historical Imports",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
