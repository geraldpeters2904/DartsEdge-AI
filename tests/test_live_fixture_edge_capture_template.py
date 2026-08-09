
import unittest
from pathlib import Path


class LiveFixtureEdgeCaptureTemplateTests(unittest.TestCase):
    def test_template_contains_capture_metrics(self):
        text = Path(
            "app/templates/live_fixture_edge_capture.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Live Odds → Fixture Edge", text)
        self.assertIn("Capture live odds now", text)
        self.assertIn("Priced rows", text)
        self.assertIn("Value rows", text)


if __name__ == "__main__":
    unittest.main()
