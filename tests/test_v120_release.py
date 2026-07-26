import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.version import MODEL_VERSION, VERSION, version_payload


class IntelligenceEngineCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_current_release_is_not_older_than_intelligence_release(self):
        major, minor, patch = (int(part) for part in VERSION.split("."))
        self.assertGreaterEqual((major, minor, patch), (1, 2, 0))

    def test_version_payload_retains_model_metadata(self):
        payload = version_payload()
        self.assertEqual(payload["model_version"], MODEL_VERSION)

    def test_version_endpoint_exposes_model_version(self):
        response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["model_version"], MODEL_VERSION)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"healthy", "degraded"})

    def test_intelligence_pages_remain_registered(self):
        paths = [
            "/player-intelligence",
            "/audit-trail",
            "/shadow-comparison",
            "/model-performance-lab",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertNotEqual(self.client.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
