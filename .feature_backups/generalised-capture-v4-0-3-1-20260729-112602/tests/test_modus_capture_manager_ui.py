import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


RESULTS_FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class ModusCaptureManagerUiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_capture_manager_page_returns_200(self):
        response = self.client.get("/admin/collector/capture/modus")

        self.assertEqual(response.status_code, 200)
        self.assertIn("MODUS Capture Manager", response.text)
        self.assertIn("Build Queue", response.text)
        self.assertIn("Series 14", response.text)

    def test_build_queue_redirects_to_active_session(self):
        with tempfile.TemporaryDirectory() as folder:
            response = self.client.post(
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

            self.assertEqual(response.status_code, 303)
            self.assertIn(
                "/admin/collector/capture/modus?folder=",
                response.headers["location"],
            )

    def test_active_session_displays_real_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            build_response = self.client.post(
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

            response = self.client.get(
                build_response.headers["location"]
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("0 / 45", response.text)
            self.assertIn("Jeff Smith", response.text)
            self.assertIn("Dawson Murschell", response.text)
            self.assertIn("match_16947.html", response.text)
            self.assertIn("Open Next Match", response.text)

    def test_refresh_moves_to_next_missing_match(self):
        with tempfile.TemporaryDirectory() as folder:
            self.client.post(
                "/admin/collector/capture/modus/build",
                data={"destination_folder": folder},
                files={
                    "results_file": (
                        "series14_week01_group_a.html",
                        RESULTS_FIXTURE.read_bytes(),
                        "text/html",
                    )
                },
            )

            Path(folder, "match_16947.html").write_text(
                "<html></html>",
                encoding="utf-8",
            )

            response = self.client.post(
                "/admin/collector/capture/modus/refresh",
                data={"destination_folder": folder},
                follow_redirects=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("1 / 45", response.text)
            self.assertIn("match_16948.html", response.text)


if __name__ == "__main__":
    unittest.main()
