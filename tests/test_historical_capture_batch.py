import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalCaptureBatchRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.results_html = FIXTURE.read_bytes()

    def test_empty_batch_page_returns_200(self):
        response = self.client.get(
            "/admin/historical-capture-batch"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Historical Capture Batch",
            response.text,
        )
        self.assertIn(
            "Build Capture Batch",
            response.text,
        )

    def test_builds_batch_from_uploaded_results_page(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.post(
                "/admin/historical-capture-batch/build",
                data={"root": root},
                files=[
                    (
                        "results_files",
                        (
                            "series14-week01-group-a.html",
                            self.results_html,
                            "text/html",
                        ),
                    )
                ],
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Open Next Group", response.text)
        self.assertIn("Series 14", response.text)
        self.assertIn("Week 1", response.text)
        self.assertIn("Group A", response.text)
        self.assertIn("MODUS ID 165", response.text)
        self.assertIn("Open Next Group", response.text)


if __name__ == "__main__":
    unittest.main()
