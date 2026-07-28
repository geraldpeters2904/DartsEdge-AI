import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.capture_library_service import CaptureLibraryService
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)


RESULTS_FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class CaptureLibraryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = RESULTS_FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.capture_service = ModusCaptureSessionService()
        self.library_service = CaptureLibraryService()

    def test_empty_root_returns_empty_library(self):
        with tempfile.TemporaryDirectory() as root:
            library = self.library_service.scan(root)

        self.assertEqual(library.entries, [])
        self.assertEqual(library.summary.sessions, 0)

    def test_discovers_existing_capture_session(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            self.capture_service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )

            library = self.library_service.scan(root)

        self.assertEqual(len(library.entries), 1)
        entry = library.entries[0]
        self.assertEqual(entry.series_label, "Series 14")
        self.assertEqual(entry.week_label, "Week 1")
        self.assertEqual(entry.group, "Group A")
        self.assertEqual(entry.captured_count, 0)
        self.assertEqual(entry.missing_count, 45)

    def test_progress_updates_without_rebuilding_queue(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            self.capture_service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )
            Path(folder, "match_16947.html").write_text(
                "<html></html>",
                encoding="utf-8",
            )

            library = self.library_service.scan(root)

        entry = library.entries[0]
        self.assertEqual(entry.captured_count, 1)
        self.assertEqual(entry.next_match_id, 16948)

    def test_summary_totals_capture_progress(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            self.capture_service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )
            Path(folder, "match_16947.html").write_text(
                "<html></html>",
                encoding="utf-8",
            )

            library = self.library_service.scan(root)

        self.assertEqual(library.summary.sessions, 1)
        self.assertEqual(library.summary.expected_matches, 45)
        self.assertEqual(library.summary.captured_matches, 1)
        self.assertEqual(library.summary.missing_matches, 44)

    def test_resume_url_targets_capture_manager(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            self.capture_service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )

            entry = self.library_service.scan(root).entries[0]

        self.assertIn("/admin/collector/capture/modus?folder=", entry.resume_url)


class CaptureLibraryRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_capture_library_page_returns_200(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/collector/captures",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Capture Library", response.text)
        self.assertIn("Scan Library", response.text)

    def test_library_page_shows_resume_link(self):
        html = RESULTS_FIXTURE.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            ModusCaptureSessionService().create_session(
                results_filename="source.html",
                results_html=html,
                destination_folder=folder,
            )

            response = self.client.get(
                "/admin/collector/captures",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Series 14", response.text)
        self.assertIn("Week 1", response.text)
        self.assertIn("Group A", response.text)
        self.assertIn("Resume", response.text)


if __name__ == "__main__":
    unittest.main()
