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

    def test_best_decision_panel_uses_effective_stake(self):
        text = CENTRE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "top_card.decision_intelligence.effective_stake",
            text,
        )

        self.assertNotIn(
            "top_card.decision_intelligence.strategy_suggested_stake",
            text,
        )

    def test_value_status_and_strategy_filters_are_separate(self):
        centre = CENTRE.read_text(
            encoding="utf-8"
        )
        card = CARD.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Value status",
            centre,
        )

        self.assertIn(
            'id="pc-strategy"',
            centre,
        )

        self.assertIn(
            '<option value="qualifies">Qualifies</option>',
            centre,
        )

        self.assertIn(
            '<option value="filtered">Filtered</option>',
            centre,
        )

        self.assertIn(
            "card.dataset.strategy === strategyValue",
            centre,
        )

        self.assertIn(
            "strategy.value = 'all'",
            centre,
        )

        self.assertIn(
            'data-strategy="{{',
            card,
        )

    def test_card_exposes_strategy_eligibility_badge(self):
        text = CARD.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "'Qualifies' if card.decision_intelligence.strategy_qualifies else 'Filtered'",
            text,
        )

        self.assertIn(
            "'good' if card.decision_intelligence.strategy_qualifies else 'warning'",
            text,
        )

    def test_bet_slip_respects_strategy_enforcement_mode(self):
        text = CARD.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "card.decision_intelligence.strategy_enforced",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.strategy_qualifies",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.effective_stake > 0",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.effective_stake",
            text,
        )

        self.assertIn(
            "Filtered by strategy.",
            text,
        )

        self.assertIn(
            "Shadow strategy advisory.",
            text,
        )

        self.assertIn(
            "card.decision_intelligence.strategy_blockers",
            text,
        )

        self.assertNotIn(
            "else 1.00",
            text,
        )

        self.assertNotIn(
            "'{:,.2f}'.format(card.assessment.recommended_stake)",
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
