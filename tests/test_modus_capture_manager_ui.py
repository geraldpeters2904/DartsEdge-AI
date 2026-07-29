import tempfile
import unittest

from fastapi.testclient import TestClient

from app.main import app


class ModusCaptureManagerUiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_capture_manager_page_returns_200(self):
        response = self.client.get(
            "/admin/collector/capture/modus"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("MODUS Capture Manager", response.text)
        self.assertIn("Build a capture queue", response.text)
        self.assertIn(
            "Series · Week · Group detected from HTML",
            response.text,
        )
        self.assertIn("Capture Library", response.text)
        self.assertIn("Build Queue", response.text)

    def test_capture_manager_no_longer_claims_week_1_only(self):
        response = self.client.get(
            "/admin/collector/capture/modus"
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "Series 14 · Week 1 · Group A",
            response.text,
        )
        self.assertIn(
            "Capture any supported MODUS Series, Week and Group",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
