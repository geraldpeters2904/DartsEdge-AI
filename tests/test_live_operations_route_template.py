import unittest
from pathlib import Path


class LiveOperationsRouteTemplateTests(
    unittest.TestCase
):
    def test_template_contains_core_panels(self):
        text = Path(
            "app/templates/live_operations.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Live Operations Centre",
            text,
        )
        self.assertIn(
            "Fixture acquisition",
            text,
        )
        self.assertIn(
            "MODUS group discovery",
            text,
        )
        self.assertIn(
            "Capture health",
            text,
        )
        self.assertIn(
            "Live opportunity pipeline",
            text,
        )
        self.assertIn(
            "Recent odds movements",
            text,
        )
        self.assertIn(
            "Operations log",
            text,
        )
        self.assertIn(
            "discovery_targets",
            text,
        )


if __name__ == "__main__":
    unittest.main()
