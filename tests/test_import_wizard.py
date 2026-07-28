import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.import_wizard_service import ImportWizardService
from tests.helpers.database import create_test_session


FIXTURE_FOLDER = str(
    Path("tests/fixtures/modus_folder_complete").resolve()
)


class ImportWizardServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ImportWizardService()

    def test_modus_connector_is_available(self):
        connector = self.service.connector("modus-official")
        self.assertTrue(connector.enabled)
        self.assertEqual(connector.input_type, "folder")

    def test_future_connectors_are_present_but_disabled(self):
        connector = self.service.connector("pdc-official")
        self.assertFalse(connector.enabled)
        self.assertEqual(connector.status_label, "Coming soon")

    def test_unknown_connector_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.connector("unknown")

    def test_modus_source_validation_returns_ready_manifest(self):
        manifest = self.service.validate_source(
            "modus-official",
            FIXTURE_FOLDER,
        )
        self.assertTrue(manifest.ready)
        self.assertEqual(manifest.expected_match_ids, [18195, 18196])

    def test_modus_preview_payload_contains_canonical_csv(self):
        payload = self.service.build_preview_payload(
            "modus-official",
            FIXTURE_FOLDER,
        )
        self.assertEqual(payload["provider"], "modus-official")
        self.assertEqual(payload["competition"], "MODUS")
        self.assertEqual(
            set(payload["csv_by_type"]),
            {"fixtures", "results", "statistics"},
        )


class ImportWizardRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_wizard_page_returns_200(self):
        response = self.client.get("/admin/collector/import")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Import Data", response.text)
        self.assertIn("MODUS Official", response.text)
        self.assertIn("PDC Official", response.text)

    def test_validate_modus_folder_renders_report(self):
        response = self.client.post(
            "/admin/collector/import/validate",
            data={
                "connector_id": "modus-official",
                "source_path": FIXTURE_FOLDER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Validation report", response.text)
        self.assertIn("Create Collector Preview", response.text)

    def test_preview_route_creates_existing_collector_preview(self):
        response = self.client.post(
            "/admin/collector/import/preview",
            data={
                "connector_id": "modus-official",
                "source_path": FIXTURE_FOLDER,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("/admin/collector/preview/", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
