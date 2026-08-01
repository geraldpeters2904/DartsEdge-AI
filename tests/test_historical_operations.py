import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchService,
)
from app.services.modus_capture_assistant_runtime import (
    capture_assistant_service,
)
from tests.helpers.database import create_test_session


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalOperationsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        if capture_assistant_service.status().running:
            capture_assistant_service.stop()

    def tearDown(self):
        if capture_assistant_service.status().running:
            capture_assistant_service.stop()

        app.dependency_overrides.clear()
        self.db.close()

    def create_batch(self, root):
        return HistoricalCaptureBatchService().create(
            root=root,
            results_pages=[
                (
                    "series14-week01-group-a.html",
                    self.results_html,
                )
            ],
        )

    def test_page_returns_200_without_batch(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/historical-operations",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Historical Operations Centre",
            response.text,
        )
        self.assertIn(
            "Build a historical capture batch.",
            response.text,
        )
        self.assertIn("Historical runner", response.text)

    def test_page_shows_current_batch_group_and_start_control(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)

            response = self.client.get(
                "/admin/historical-operations",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Series 14", response.text)
        self.assertIn("Week 1", response.text)
        self.assertIn("Group A", response.text)
        self.assertIn("Start Workflow", response.text)
        self.assertIn("Historical import status", response.text)

    def test_start_pause_resume_and_stop_workflow(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)

            with tempfile.TemporaryDirectory() as watch:
                started = self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/start"
                    ),
                    data={
                        "root": root,
                        "watch_folder": watch,
                    },
                    follow_redirects=True,
                )

                self.assertEqual(started.status_code, 200)
                self.assertIn(
                    "Historical workflow and worker started.",
                    started.text,
                )
                self.assertIn("Pause Workflow", started.text)
                self.assertTrue(
                    capture_assistant_service.status().running
                )

                paused = self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/pause"
                    ),
                    data={"root": root},
                    follow_redirects=True,
                )

                self.assertEqual(paused.status_code, 200)
                self.assertIn(
                    "Historical workflow paused.",
                    paused.text,
                )
                self.assertIn("Resume Workflow", paused.text)
                self.assertFalse(
                    capture_assistant_service.status().running
                )

                resumed = self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/resume"
                    ),
                    data={
                        "root": root,
                        "watch_folder": watch,
                    },
                    follow_redirects=True,
                )

                self.assertEqual(resumed.status_code, 200)
                self.assertIn(
                    "Historical workflow and worker resumed.",
                    resumed.text,
                )
                self.assertIn("Stop Workflow", resumed.text)
                self.assertTrue(
                    capture_assistant_service.status().running
                )

                stopped = self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/stop"
                    ),
                    data={"root": root},
                    follow_redirects=True,
                )

                self.assertEqual(stopped.status_code, 200)
                self.assertIn(
                    "Historical workflow and worker stopped.",
                    stopped.text,
                )
                self.assertIn("Start Workflow", stopped.text)
                self.assertFalse(
                    capture_assistant_service.status().running
                )

    def test_status_endpoint_reports_worker_state(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)

            response = self.client.get(
                "/admin/historical-operations/status",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["runner_status"],
            "stopped",
        )
        self.assertFalse(payload["worker_running"])
        self.assertIn("worker_iterations", payload)

    def test_start_route_starts_background_worker(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)

            with tempfile.TemporaryDirectory() as watch:
                response = self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/start"
                    ),
                    data={
                        "root": root,
                        "watch_folder": watch,
                    },
                    follow_redirects=True,
                )

                status_response = self.client.get(
                    "/admin/historical-operations/status",
                    params={"root": root},
                )

                self.client.post(
                    (
                        "/admin/historical-operations/"
                        "workflow/stop"
                    ),
                    data={"root": root},
                    follow_redirects=True,
                )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Historical workflow and worker started.",
            response.text,
        )

        payload = status_response.json()

        self.assertEqual(
            payload["runner_status"],
            "running",
        )
        self.assertTrue(payload["worker_running"])
        self.assertTrue(payload["assistant_running"])

    def test_page_includes_live_status_polling(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)

            response = self.client.get(
                "/admin/historical-operations",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "pollHistoricalOperations",
            response.text,
        )
        self.assertIn(
            "/admin/historical-operations/status",
            response.text,
        )
        self.assertIn(
            "window.location.reload()",
            response.text,
        )
        self.assertIn(
            "processedMatches",
            response.text,
        )



if __name__ == "__main__":
    unittest.main()
