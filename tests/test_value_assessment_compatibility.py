import unittest

from app.services.expected_value_service import ValueAssessment, assess_value


class ValueAssessmentCompatibilityTests(unittest.TestCase):
    def _assessment(self, probability=60):
        return assess_value(
            model_probability=probability,
            decimal_odds=2.0,
            bookmaker="Test Book",
            bankroll=1000,
            kelly_fraction=0.25,
            max_daily_risk_percent=5,
        )

    def test_is_value_alias_matches_has_value(self):
        assessment = self._assessment()
        self.assertEqual(assessment.is_value, assessment.has_value)

    def test_suggested_stake_alias_matches_recommended_stake(self):
        assessment = self._assessment()
        self.assertEqual(assessment.suggested_stake, assessment.recommended_stake)

    def test_aliases_work_for_pass_assessment(self):
        assessment = self._assessment(probability=40)
        self.assertFalse(assessment.is_value)
        self.assertEqual(assessment.suggested_stake, 0.0)

    def test_aliases_are_read_only(self):
        assessment = ValueAssessment(
            model_probability=55,
            decimal_odds=2.0,
            implied_probability=50,
            edge_percent=5,
            expected_value_percent=10,
            fair_odds=1.818,
            bookmaker="Test Book",
            recommended_stake=10,
            kelly_percent=1,
            has_value=True,
            decision="Consider",
            risk_level="Low",
        )
        with self.assertRaises(AttributeError):
            assessment.is_value = False
        with self.assertRaises(AttributeError):
            assessment.suggested_stake = 0


if __name__ == "__main__":
    unittest.main()
