import unittest
from pathlib import Path


class FixtureEdgeTemplateTests(unittest.TestCase):
    def test_template_contains_core_metrics(self):
        text = Path(
            "app/templates/fixture_edge.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Prediction · Fair Odds · Edge",
            text,
        )

        self.assertIn(
            "Fair odds",
            text,
        )

        self.assertIn(
            "Market odds",
            text,
        )

        self.assertIn(
            "Verdict",
            text,
        )


if __name__ == "__main__":
    unittest.main()
