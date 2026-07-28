import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)


RESULTS_FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class ModusCapturePolishServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusCaptureSessionService()
        self.html = RESULTS_FIXTURE.read_text(encoding="utf-8")

    def test_progress_percent_starts_at_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )
            self.assertEqual(session.progress_percent, 0)

    def test_progress_percent_updates_after_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="source.html",
                results_html=self.html,
                destination_folder=folder,
            )
            for match_id in range(16947, 16957):
                Path(folder, f"match_{match_id}.html").write_text("<html></html>")

            session = self.service.refresh_session(folder)
            self.assertEqual(session.captured_count, 10)
            self.assertEqual(session.progress_percent, 22)


class ModusCapturePolishRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _build_session(self, folder):
        return self.client.post(
            "/admin/collector/capture/modus/build",
            data={"destination_folder": folder},
            files={
                "results_file": (
                    "series14_week01_group_a.html",
                    RESULTS_FIXTURE.read_bytes(),
                    "text/html",
                )
            },
            follow_redirects=False,
        )

    def test_page_shows_progress_bar(self):
        with tempfile.TemporaryDirectory() as folder:
            response = self._build_session(folder)
            page = self.client.get(response.headers["location"])

            self.assertEqual(page.status_code, 200)
            self.assertIn("capture-progress-track", page.text)
            self.assertIn("0%", page.text)
            self.assertIn("Open Folder", page.text)

    @patch("app.routes.modus_capture_manager.subprocess.run")
    def test_open_folder_route_invokes_macos_open(self, mock_run):
        with tempfile.TemporaryDirectory() as folder:
            response = self.client.post(
                "/admin/collector/capture/modus/open-folder",
                data={"destination_folder": folder},
                follow_redirects=False,
            )

            self.assertEqual(response.status_code, 303)
            mock_run.assert_called_once()
            command = mock_run.call_args.args[0]
            self.assertEqual(command[0], "open")
            self.assertEqual(command[1], str(Path(folder).resolve()))

    def test_validate_incomplete_folder_reports_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            self._build_session(folder)

            response = self.client.post(
                "/admin/collector/capture/modus/validate",
                data={"destination_folder": folder},
                follow_redirects=False,
            )

            self.assertEqual(response.status_code, 303)
            self.assertIn("validation%20issues", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
