import unittest
from pathlib import Path


CENTRE = Path(
    "app/templates/prediction_centre.html"
)

CARD = Path(
    "app/templates/components/pro_prediction_card.html"
)


class PredictionCentreDecisionUITests(
    unittest.TestCase
):
    def test_decision_score_is_default_sort(self):
        text = CENTRE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '<option value="decision" selected>Decision Score</option>',
            text,
        )

        self.assertIn(
            "'decision'",
            text,
        )

        self.assertIn(
            "sort.value = 'decision'",
            text,
        )

    def test_card_exposes_decision_sort_attribute(self):
        text = CARD.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "data-decision",
            text,
        )

        self.assertIn(
            "Decision Intelligence",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.score",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.breakdown.value",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.breakdown.market",
            text,
        )

    def test_best_decision_panel_is_available(self):
        text = CENTRE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'id="best-decision-today"',
            text,
        )

        self.assertIn(
            "Highest Decision Intelligence score",
            text,
        )

    def test_unpriced_card_explains_missing_score(self):
        text = CARD.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Decision Score awaiting bookmaker odds",
            text,
        )


if __name__ == "__main__":
    unittest.main()
