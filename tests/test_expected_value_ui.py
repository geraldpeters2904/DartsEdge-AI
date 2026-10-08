import unittest
from pathlib import Path


class ExpectedValueUITests(unittest.TestCase):

    def test_kelly_reference_and_effective_stake_are_distinct(self):
        template = Path("app/templates/expected_value.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("<span>Kelly Reference</span>", template)
        self.assertIn("assessment.recommended_stake", template)
        self.assertIn("decision_engine.effective_stake", template)
        self.assertIn("decision_engine.official_stake", template)
        self.assertIn("decision_engine.strategy_stake", template)

    def test_enforcement_modes_remain_explained(self):
        template = Path("app/templates/expected_value.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("decision_engine.enforced", template)
        self.assertIn("Active enforcement is enabled", template)
        self.assertIn("Shadow mode is enabled", template)


if __name__ == "__main__":
    unittest.main()
