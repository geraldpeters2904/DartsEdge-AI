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


class ModusCaptureManagerStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(encoding="utf-8")
        cls.client = TestClient(app)

    def test_status_reports_current_capture_progress(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Group_A"

            session = ModusCaptureSessionService().create_session(
                results_filename="results.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            response = self.client.get(
                "/admin/collector/capture/modus/status",
                params={"folder": str(folder)},
            )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["expected_count"],
            session.expected_count,
        )
        self.assertEqual(payload["captured_count"], 0)
        self.assertEqual(
            payload["missing_count"],
            session.expected_count,
        )
        self.assertFalse(payload["complete"])
        self.assertIsNotNone(payload["next_match_id"])
        self.assertIsNotNone(payload["next_source_url"])

    def test_status_advances_after_expected_file_is_added(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Group_A"

            service = ModusCaptureSessionService()
            session = service.create_session(
                results_filename="results.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            first_match_id = session.next_item.match_id
            first_filename = session.next_item.destination_filename

            Path(folder, first_filename).write_text(
                "<html>captured match page</html>",
                encoding="utf-8",
            )

            response = self.client.get(
                "/admin/collector/capture/modus/status",
                params={"folder": str(folder)},
            )

        payload = response.json()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["captured_count"], 1)
        self.assertNotEqual(
            payload["next_match_id"],
            first_match_id,
        )

    def test_status_returns_safe_error_for_missing_folder(self):
        response = self.client.get(
            "/admin/collector/capture/modus/status",
            params={"folder": "/folder/that/does/not/exist"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertIn("error", response.json())


if __name__ == "__main__":
    unittest.main()
