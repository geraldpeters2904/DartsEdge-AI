import unittest

from app.services.decision_intelligence_service import (
    build_decision_intelligence,
)


class DecisionIntelligenceConsensusTests(unittest.TestCase):
    def build(self, **overrides):
        values = {
            "model_probability": 62.0,
            "model_confidence": 78.0,
            "expected_value_percent": 10.0,
            "edge_percent": 8.0,
            "suggested_stake": 20.0,
            "bankroll": 1000.0,
            "evidence_score": 82.0,
            "trust_score": 74.0,
            "portfolio_exposure_percent": 2.0,
            "maximum_portfolio_exposure_percent": 10.0,
            "market_direction": "stable",
            "market_volatility": "medium",
            "clv_percent": None,
            "strategy_qualifies": True,
        }
        values.update(overrides)
        return build_decision_intelligence(**values)

    def test_strong_consensus_improves_market_score(self):
        baseline = self.build()

        supported = self.build(
            consensus_score=92.0,
            steam_direction="shortening",
            steam_strength="strong",
            coordinated_move=True,
        )

        self.assertGreater(
            supported.breakdown.market,
            baseline.breakdown.market,
        )

        self.assertGreater(
            supported.score,
            baseline.score,
        )

    def test_coordinated_drift_reduces_market_score(self):
        baseline = self.build()

        opposed = self.build(
            consensus_score=90.0,
            steam_direction="drifting",
            steam_strength="strong",
            coordinated_move=True,
        )

        self.assertLess(
            opposed.breakdown.market,
            baseline.breakdown.market,
        )

        self.assertIn(
            "Coordinated strong drift moves against the selection.",
            opposed.caution_reasons,
        )

    def test_weak_consensus_is_penalised(self):
        baseline = self.build()

        weak = self.build(
            consensus_score=30.0,
        )

        self.assertLess(
            weak.breakdown.market,
            baseline.breakdown.market,
        )

        self.assertIn(
            "Bookmaker prices show weak consensus.",
            weak.caution_reasons,
        )


if __name__ == "__main__":
    unittest.main()
