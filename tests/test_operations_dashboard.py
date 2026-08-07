import tempfile
import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.routes import operations as operations_route
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)
from tests.helpers.database import create_test_session


class FakeWorkflowStatus:
    status = "running"
    current_match_id = 16958


class FakeWorkflowService:
    def __init__(self):
        self.root = None
        self.summary = CaptureIterationSummary(
            started_at=datetime(2026, 8, 3, 9, 5, 0),
            finished_at=datetime(2026, 8, 3, 9, 5, 5),
            status="running",
            matches_captured=1,
            bytes_written=7004,
        )

    def capture_iteration(self, root):
        self.root = root
        return FakeWorkflowStatus()

    def latest_capture_summary(self):
        return self.summary


class OperationsDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_operations_dashboard_returns_200(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Operations Dashboard", response.text)
        self.assertIn("Active capture", response.text)
        self.assertIn("Warehouse totals", response.text)
        self.assertIn("System checks", response.text)

    def test_operations_dashboard_has_workflow_links(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "/admin/collector/capture/modus",
            response.text,
        )
        self.assertIn(
            "/admin/historical-imports",
            response.text,
        )
        self.assertIn(
            "/admin/warehouse-dashboard",
            response.text,
        )

    def test_operations_dashboard_shows_assistant_status(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)

        self.assertIn("Capture Assistant", response.text)
        self.assertIn("Automation status", response.text)
        self.assertIn("Open Full Assistant", response.text)

    def test_operations_dashboard_shows_import_pipeline(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "Historical queue and engine",
            response.text,
        )
        self.assertIn("Build Import Queue", response.text)

    def test_run_capture_iteration_redirects_with_result(self):
        original_service = (
            operations_route
            .historical_workflow_worker
            .workflow_service
        )
        fake_service = FakeWorkflowService()

        operations_route.historical_workflow_worker.workflow_service = (
            fake_service
        )

        try:
            with tempfile.TemporaryDirectory() as root:
                response = self.client.post(
                    "/operations/capture-iteration",
                    data={"capture_root": root},
                    follow_redirects=False,
                )

            self.assertEqual(response.status_code, 303)
            self.assertEqual(fake_service.root, root)
            self.assertIn(
                "7004%20bytes%20written",
                response.headers["location"],
            )
            self.assertIn(
                "Next%20match%3A%2016958",
                response.headers["location"],
            )
        finally:
            operations_route.historical_workflow_worker.workflow_service = (
                original_service
            )

    def test_dashboard_contains_run_iteration_button(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'action="/operations/capture-iteration"',
            response.text,
        )
        self.assertIn("Run One Iteration", response.text)

    def test_operations_dashboard_shows_capture_history(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/operations",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("CAPTURE HISTORY", response.text)
        self.assertIn("Capture performance", response.text)
        self.assertIn(
            "OPERATIONS TIMELINE",
            response.text,
        )
        self.assertIn(
            "Recent capture activity",
            response.text,
        )
        self.assertIn("Success rate", response.text)


if __name__ == "__main__":
    unittest.main()
