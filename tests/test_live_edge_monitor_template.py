
import unittest
from pathlib import Path


class LiveEdgeMonitorTemplateTests(unittest.TestCase):
    def test_template_contains_monitor_metrics(self):
        text = Path(
            "app/templates/live_edge_monitor.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Automatic Live Odds Monitor",
            text,
        )
        self.assertIn(
            "Last priced rows",
            text,
        )
        self.assertIn(
            "Run live edge now",
            text,
        )


if __name__ == "__main__":
    unittest.main()
