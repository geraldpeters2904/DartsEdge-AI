import warnings
import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.version import BUILD, RELEASE_NAME, VERSION


class V140ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_release_metadata(self):
        self.assertEqual(VERSION, "1.4.0")
        self.assertEqual(BUILD, "001")
        self.assertEqual(RELEASE_NAME, "Strategy Engine")

    def test_version_endpoint(self):
        payload = self.client.get("/version").json()
        self.assertEqual(payload["version"], "1.4.0")
        self.assertEqual(payload["release"], "Strategy Engine")

    def test_strategy_pages_are_available(self):
        for path in ("/strategies", "/strategy-editor", "/strategy-analytics", "/expected-value"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_diagnostics_include_strategy_engine(self):
        response = self.client.get("/diagnostics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Strategy Engine", response.text)

    def test_template_rendering_emits_no_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            response = self.client.get("/daily-briefing")
        self.assertEqual(response.status_code, 200)
        relevant = [
            item
            for item in caught
            if issubclass(item.category, DeprecationWarning)
            and "TemplateResponse" in str(item.message)
        ]
        self.assertEqual(relevant, [])


if __name__ == "__main__":
    unittest.main()
