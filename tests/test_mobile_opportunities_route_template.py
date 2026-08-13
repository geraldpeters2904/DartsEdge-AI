import unittest
from pathlib import Path


class MobileOpportunitiesRouteTemplateTests(
    unittest.TestCase
):
    def test_template_contains_mobile_recommendation_fields(self):
        text = Path(
            "app/templates/mobile_opportunities.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "DartsEdge Opportunities",
            text,
        )
        self.assertIn(
            "Model probability",
            text,
        )
        self.assertIn(
            "Bookmaker price",
            text,
        )
        self.assertIn(
            "Expected value",
            text,
        )
        self.assertIn(
            "Suggested stake",
            text,
        )
        self.assertIn(
            "Safety:",
            text,
        )
        self.assertIn(
            "decision_safety_explanation",
            text,
        )


if __name__ == "__main__":
    unittest.main()
