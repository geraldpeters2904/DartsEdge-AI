import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app


class DashboardPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.root = Path(__file__).resolve().parents[1]

    def test_core_pages_render(self):
        for path in ("/mission-control", "/opportunities", "/portfolio-health", "/ai-coach", "/dashboard"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_active_navigation_is_rendered(self):
        response = self.client.get("/ai-coach")
        self.assertIn('href="/ai-coach" class="active"', response.text)

    def test_stylesheet_contains_responsive_layout(self):
        css = (self.root / "app/static/css/styles.css").read_text()
        self.assertIn("@media (max-width: 700px)", css)
        self.assertIn(".opportunity-table-wrap", css)
        self.assertIn("focus-visible", css)

    def test_stylesheet_version_bumped(self):
        response = self.client.get("/mission-control")
        self.assertIn("styles.css?v=11", response.text)


if __name__ == "__main__":
    unittest.main()
