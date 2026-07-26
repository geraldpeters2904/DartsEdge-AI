import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.version import BUILD, VERSION, version_payload


class ReleaseStabilizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_version_metadata(self):
        payload = version_payload()
        self.assertEqual(payload["version"], VERSION)
        self.assertEqual(payload["build"], BUILD)

    def test_version_endpoint(self):
        response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], VERSION)
        self.assertEqual(response.json()["build"], BUILD)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"healthy", "degraded"})
        self.assertTrue(response.json()["checks"])

    def test_diagnostics_page(self):
        response = self.client.get("/diagnostics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Diagnostics", response.text)
        self.assertIn(f"Build {BUILD}", response.text)

    def test_primary_pages_remain_available(self):
        for path in ("/mission-control", "/opportunities", "/portfolio-health", "/ai-coach", "/dashboard"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
