import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.version import BUILD, MODEL_VERSION, RELEASE_NAME, VERSION, version_payload


class V120ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_release_metadata(self):
        self.assertEqual(VERSION, "1.2.0")
        self.assertEqual(BUILD, "001")
        self.assertEqual(RELEASE_NAME, "Intelligence Engine")
        self.assertEqual(MODEL_VERSION, "Intelligence-0.1-shadow")

    def test_version_payload_includes_model(self):
        payload = version_payload()
        self.assertEqual(payload["version"], "1.2.0")
        self.assertEqual(payload["model_version"], MODEL_VERSION)

    def test_version_endpoint(self):
        response = self.client.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["release"], "Intelligence Engine")

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["status"], {"healthy", "degraded"})

    def test_intelligence_pages_are_registered(self):
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
