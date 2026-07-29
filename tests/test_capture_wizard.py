import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.capture_wizard_service import CaptureWizardService


RESULTS_FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class CaptureWizardServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = RESULTS_FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.service = CaptureWizardService()

    def test_creates_standard_folder_structure(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.create_from_pages(
                capture_root=root,
                saved_pages=[("week1-group-a.html", self.html)],
            )

            self.assertEqual(result.created_count, 1)
            created = result.created[0]
            self.assertEqual(
                created.destination_folder,
                Path(root).resolve()
                / "Series_14"
                / "Week_01"
                / "Group_A",
            )
            self.assertTrue(
                (created.destination_folder / "results.html").exists()
            )

    def test_created_session_has_real_queue(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.create_from_pages(
                capture_root=root,
                saved_pages=[("week1-group-a.html", self.html)],
            )

            created = result.created[0]
            self.assertEqual(created.expected_count, 45)
            self.assertEqual(created.captured_count, 0)
            self.assertIn(
                "/admin/collector/capture/modus?folder=",
                created.resume_url,
            )

    def test_duplicate_uploaded_context_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.create_from_pages(
                capture_root=root,
                saved_pages=[
                    ("first.html", self.html),
                    ("second.html", self.html),
                ],
            )

            self.assertEqual(result.created_count, 1)
            self.assertEqual(result.error_count, 1)
            self.assertIn("More than one", result.errors[0])

    def test_invalid_page_is_reported_without_blocking_valid_page(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.create_from_pages(
                capture_root=root,
                saved_pages=[
                    ("valid.html", self.html),
                    ("invalid.html", "<html>broken</html>"),
                ],
            )

            self.assertEqual(result.created_count, 1)
            self.assertEqual(result.error_count, 1)

    def test_no_pages_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "at least one"):
                self.service.create_from_pages(
                    capture_root=root,
                    saved_pages=[],
                )


class CaptureWizardRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_wizard_page_returns_200(self):
        response = self.client.get("/admin/collector/captures/new")

        self.assertEqual(response.status_code, 200)
        self.assertIn("New Capture Wizard", response.text)
        self.assertIn("Create Capture Sessions", response.text)

    def test_post_creates_session_and_renders_result(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.post(
                "/admin/collector/captures/new",
                data={"capture_root": root},
                files=[
                    (
                        "results_files",
                        (
                            "week1-group-a.html",
                            RESULTS_FIXTURE.read_bytes(),
                            "text/html",
                        ),
                    )
                ],
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("1 capture session(s) created", response.text)
            self.assertIn("Open Capture", response.text)


if __name__ == "__main__":
    unittest.main()
