import csv
import io
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.modus_fixture_import_service import (
    ModusFixtureImportService,
)
from tests.helpers.database import create_test_session


UPCOMING = Path(
    "tests/fixtures/modus_fixture_lifecycle/upcoming.html"
)
COMPLETED = Path(
    "tests/fixtures/modus_fixture_lifecycle/completed.html"
)


class ModusFixtureImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusFixtureImportService()

    def test_builds_fixture_only_payload(self):
        payload = self.service.build_payload(
            UPCOMING.read_text(encoding="utf-8")
        )

        self.assertEqual(set(payload.csv_by_type), {"fixtures"})
        self.assertEqual(payload.fixture_count, 1)
        self.assertEqual(payload.scheduled_count, 1)
        self.assertEqual(payload.completed_count, 0)

    def test_upcoming_csv_has_scheduled_status_and_stable_id(self):
        payload = self.service.build_payload(
            UPCOMING.read_text(encoding="utf-8")
        )
        rows = list(
            csv.DictReader(io.StringIO(payload.csv_by_type["fixtures"]))
        )

        self.assertEqual(rows[0]["external_id"], "modus-match-20001")
        self.assertEqual(rows[0]["status"], "scheduled")
        self.assertEqual(rows[0]["source_provider"], "modus-official")

    def test_completed_page_keeps_same_match_id(self):
        upcoming = self.service.build_payload(
            UPCOMING.read_text(encoding="utf-8")
        )
        completed = self.service.build_payload(
            COMPLETED.read_text(encoding="utf-8")
        )

        self.assertEqual(
            upcoming.fixtures[0].external_id,
            completed.fixtures[0].external_id,
        )
        self.assertEqual(
            completed.fixtures[0].status.value,
            "completed",
        )


class ModusFixtureImportRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_fixture_import_page_returns_200(self):
        response = self.client.get(
            "/admin/collector/import/modus-fixtures"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Import MODUS Fixtures", response.text)
        self.assertIn("Create Fixture Preview", response.text)

    def test_upcoming_page_creates_collector_preview(self):
        response = self.client.post(
            "/admin/collector/import/modus-fixtures/preview",
            files={
                "results_file": (
                    "upcoming.html",
                    UPCOMING.read_bytes(),
                    "text/html",
                )
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn(
            "/admin/collector/preview/",
            response.headers["location"],
        )


if __name__ == "__main__":
    unittest.main()
