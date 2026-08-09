import unittest
from pathlib import Path


class LiveOperationsRouteTemplateTests(unittest.TestCase):
    def test_template_contains_core_panels(self):
        text = Path(
            "app/templates/live_operations.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn("Live Operations Centre", text)
        self.assertIn("Capture health", text)
        self.assertIn("Recent odds movements", text)
        self.assertIn("Operations log", text)


if __name__ == "__main__":
    unittest.main()
