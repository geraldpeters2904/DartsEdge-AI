import unittest

from app.services.live_opportunity_centre_service import (
    LiveOpportunity,
)


class LiveOpportunityDecisionSafetyMetadataTests(
    unittest.TestCase
):
    def test_defaults_are_observational_and_safe(self):
        opportunity = LiveOpportunity(
            fixture_id=1,
            fixture_date=None,
            tournament="MODUS",
            player_a="Alpha",
            player_b="Bravo",
            selection="Alpha",
            bookmaker=None,
            decimal_odds=None,
            decision_score=80,
            decision_grade="Excellent",
            recommendation="BET",
            model_probability=67.0,
            model_confidence=75.0,
            expected_value_percent=5.0,
            edge_percent=3.0,
            consensus_score=None,
            steam_direction=None,
            steam_strength=None,
            coordinated_move=False,
            suggested_stake=0.0,
            lifecycle_state="NEW",
            age_minutes=0,
        )

        self.assertEqual(
            opportunity.decision_safety_state,
            "UNKNOWN",
        )
        self.assertTrue(
            opportunity.decision_safety_caution
        )
        self.assertFalse(
            opportunity.decision_safety_high_caution
        )
        self.assertIsNone(
            opportunity.decision_safety_trust_score
        )
        self.assertIsNone(
            opportunity.decision_safety_explanation
        )

    def test_high_caution_metadata_is_retained(self):
        opportunity = LiveOpportunity(
            fixture_id=1,
            fixture_date=None,
            tournament="MODUS",
            player_a="Alpha",
            player_b="Bravo",
            selection="Alpha",
            bookmaker=None,
            decimal_odds=None,
            decision_score=80,
            decision_grade="Excellent",
            recommendation="BET",
            model_probability=67.0,
            model_confidence=75.0,
            expected_value_percent=5.0,
            edge_percent=3.0,
            consensus_score=None,
            steam_direction=None,
            steam_strength=None,
            coordinated_move=False,
            suggested_stake=0.0,
            lifecycle_state="NEW",
            age_minutes=0,
            decision_safety_state="HIGH_CAUTION",
            decision_safety_caution=True,
            decision_safety_high_caution=True,
            decision_safety_trust_score=72.0,
            decision_safety_explanation=(
                "High sparse-consensus regime risk."
            ),
        )

        self.assertEqual(
            opportunity.decision_safety_state,
            "HIGH_CAUTION",
        )
        self.assertTrue(
            opportunity.decision_safety_high_caution
        )
        self.assertEqual(
            opportunity.decision_safety_trust_score,
            72.0,
        )

        # Safety metadata must remain observational.
        self.assertEqual(
            opportunity.decision_score,
            80,
        )
        self.assertEqual(
            opportunity.recommendation,
            "BET",
        )
        self.assertEqual(
            opportunity.expected_value_percent,
            5.0,
        )


if __name__ == "__main__":
    unittest.main()
