import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.import_wizard_service import ImportWizardService
from app.services.modus_canonical_builder import ModusCanonicalBuilder
from app.services.modus_folder_service import ModusFolderImportService


FIXTURES = Path("tests/fixtures")
COMPLETE = FIXTURES / "modus_folder_complete"
INCOMPLETE = FIXTURES / "modus_folder_incomplete"


class PartialAcceptanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.folder_service = ModusFolderImportService()
        self.builder = ModusCanonicalBuilder()
        self.wizard = ImportWizardService()

    def test_incomplete_folder_remains_not_ready_in_normal_mode(self):
        manifest = self.folder_service.inspect(INCOMPLETE)

        self.assertFalse(manifest.ready)
        self.assertTrue(manifest.partial_ready)
        self.assertTrue(
            any(
                issue.code == "missing_match_page"
                and issue.severity == "error"
                for issue in manifest.issues
            )
        )

    def test_partial_mode_accepts_valid_captured_pages(self):
        manifest = self.folder_service.inspect(
            INCOMPLETE,
            allow_partial=True,
        )

        self.assertFalse(manifest.ready)
        self.assertTrue(manifest.partial_ready)
        self.assertEqual(manifest.validated_match_ids, [18195])
        self.assertTrue(
            any(
                issue.code == "missing_match_page"
                and issue.severity == "warning"
                for issue in manifest.issues
            )
        )

    def test_partial_builder_only_builds_validated_pages(self):
        build = self.builder.build(
            INCOMPLETE,
            allow_partial=True,
        )

        self.assertTrue(build.ready)
        self.assertEqual(len(build.fixtures), 1)
        self.assertEqual(len(build.results), 1)
        self.assertEqual(len(build.statistics), 2)
        self.assertEqual(
            build.fixtures[0].external_id,
            "modus-match-18195",
        )

    def test_normal_builder_still_rejects_incomplete_folder(self):
        with self.assertRaisesRegex(ValueError, "full canonical build"):
            self.builder.build(INCOMPLETE)

    def test_wizard_payload_supports_partial_mode(self):
        payload = self.wizard.build_preview_payload(
            "modus-official",
            str(INCOMPLETE),
            allow_partial=True,
        )

        self.assertEqual(payload["summary"]["fixture_count"], 1)
        self.assertEqual(payload["summary"]["result_count"], 1)
        self.assertEqual(payload["summary"]["statistics_count"], 2)


class PartialAcceptanceRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_import_page_shows_acceptance_mode(self):
        response = self.client.get("/admin/collector/import")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Acceptance mode", response.text)
        self.assertIn(
            "Validate and preview only the captured match pages",
            response.text,
        )

    def test_partial_validation_renders_ready_state(self):
        response = self.client.post(
            "/admin/collector/import/validate",
            data={
                "connector_id": "modus-official",
                "source_path": str(INCOMPLETE.resolve()),
                "acceptance_mode": "partial",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Partial acceptance ready", response.text)
        self.assertIn("Captured pages passed", response.text)
        self.assertIn("Create Collector Preview", response.text)


if __name__ == "__main__":
    unittest.main()
