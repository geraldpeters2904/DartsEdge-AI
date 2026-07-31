import tempfile
import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from tests.helpers.database import create_test_session


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

        self.assertIn("/admin/collector/capture/modus", response.text)
        self.assertIn("/admin/historical-imports", response.text)
        self.assertIn("/admin/warehouse-dashboard", response.text)

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



if __name__ == "__main__":
    unittest.main()
