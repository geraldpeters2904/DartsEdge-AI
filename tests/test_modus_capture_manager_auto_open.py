import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)


FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class ModusCaptureManagerAutoOpenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.results_html = FIXTURE.read_text(encoding="utf-8")

    def test_active_session_renders_auto_open_controls(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Group_A"

            ModusCaptureSessionService().create_session(
                results_filename="results.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            response = self.client.get(
                "/admin/collector/capture/modus",
                params={"folder": str(folder)},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="auto-open-toggle"', response.text)
        self.assertIn("Enable Auto-open", response.text)
        self.assertIn("dartsedgeAutoOpenNextMatch", response.text)
        self.assertIn("status.next_source_url", response.text)
        self.assertIn("window.location.reload()", response.text)


if __name__ == "__main__":
    unittest.main()
