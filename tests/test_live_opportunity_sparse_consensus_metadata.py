import unittest

from app.services.live_opportunity_centre_service import (
    LiveOpportunity,
)


class LiveOpportunitySparseConsensusMetadataTests(
    unittest.TestCase
):
    def test_defaults_preserve_existing_callers(self):
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
            decision_grade="A",
            recommendation="WATCH",
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

        self.assertIsNone(
            opportunity.sparse_consensus_density
        )

        self.assertEqual(
            opportunity.sparse_consensus_risk_state,
            "UNKNOWN",
        )

        self.assertFalse(
            opportunity.sparse_consensus_risk_elevated
        )

        self.assertFalse(
            opportunity.sparse_consensus_risk_high
        )

        self.assertIsNone(
            opportunity.sparse_consensus_risk_explanation
        )

    def test_explicit_risk_metadata_is_retained(self):
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
            decision_grade="A",
            recommendation="WATCH",
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
            sparse_consensus_density=5.921053,
            sparse_consensus_risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            sparse_consensus_risk_elevated=True,
            sparse_consensus_risk_high=True,
            sparse_consensus_risk_explanation=(
                "Sparse-consensus density is above 3%."
            ),
        )

        self.assertEqual(
            opportunity.sparse_consensus_density,
            5.921053,
        )

        self.assertEqual(
            opportunity.sparse_consensus_risk_state,
            "HIGH_SPARSE_CONSENSUS_RISK",
        )

        self.assertTrue(
            opportunity.sparse_consensus_risk_elevated
        )

        self.assertTrue(
            opportunity.sparse_consensus_risk_high
        )

    def test_risk_metadata_does_not_change_sort_fields(self):
        normal = LiveOpportunity(
            fixture_id=1,
            fixture_date=None,
            tournament="MODUS",
            player_a="Alpha",
            player_b="Bravo",
            selection="Alpha",
            bookmaker=None,
            decimal_odds=None,
            decision_score=80,
            decision_grade="A",
            recommendation="WATCH",
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
            sparse_consensus_risk_state="NORMAL",
        )

        high = LiveOpportunity(
            fixture_id=2,
            fixture_date=None,
            tournament="MODUS",
            player_a="Charlie",
            player_b="Delta",
            selection="Charlie",
            bookmaker=None,
            decimal_odds=None,
            decision_score=80,
            decision_grade="A",
            recommendation="WATCH",
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
            sparse_consensus_risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            sparse_consensus_risk_elevated=True,
            sparse_consensus_risk_high=True,
        )

        self.assertEqual(
            normal.decision_score,
            high.decision_score,
        )

        self.assertEqual(
            normal.expected_value_percent,
            high.expected_value_percent,
        )

        self.assertEqual(
            normal.edge_percent,
            high.edge_percent,
        )


if __name__ == "__main__":
    unittest.main()
