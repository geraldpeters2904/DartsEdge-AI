import unittest

from app.services.expected_value_service import ValueAssessment, assess_value


class ValueAssessmentCompatibilityTests(unittest.TestCase):
    def test_positive_assessment_exposes_is_value_alias(self):
        assessment = assess_value(
            model_probability=60,
            decimal_odds=2.0,
            bookmaker="Test Book",
            bankroll=1000,
            kelly_fraction=0.25,
            max_daily_risk_percent=5,
        )
        self.assertTrue(assessment.has_value)
        self.assertEqual(assessment.is_value, assessment.has_value)

    def test_pass_assessment_exposes_is_value_alias(self):
        assessment = assess_value(
            model_probability=40,
            decimal_odds=2.0,
            bookmaker="Test Book",
            bankroll=1000,
            kelly_fraction=0.25,
            max_daily_risk_percent=5,
        )
        self.assertFalse(assessment.has_value)
        self.assertEqual(assessment.is_value, assessment.has_value)

    def test_alias_is_read_only(self):
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


if __name__ == "__main__":
    unittest.main()
