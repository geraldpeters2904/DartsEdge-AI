import unittest

from app.services.decision_intelligence_service import (
    build_decision_intelligence,
    decision_intelligence_summary,
)


class DecisionIntelligenceServiceTests(unittest.TestCase):
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
            "market_direction": "shortening",
            "market_volatility": "low",
            "clv_percent": 2.5,
            "strategy_qualifies": True,
        }

        values.update(overrides)

        return build_decision_intelligence(**values)

    def test_strong_signals_create_strong_score(self):
        report = self.build()

        # These inputs are intentionally "strong" rather than "premium".
        # EV is 10% against a 20% scoring target and edge is 8% against
        # a 15% scoring target, so a score in the 70s is expected.
        self.assertGreaterEqual(
            report.score,
            70,
        )

        self.assertIn(
            report.recommendation,
            {
                "BET",
                "SMALL BET",
            },
        )

        self.assertGreaterEqual(
            report.stars,
            3,
        )

    def test_strategy_blocker_caps_score(self):
        report = self.build(
            strategy_qualifies=False,
            strategy_blockers=(
                "EV is below strategy minimum",
            ),
        )

        self.assertLessEqual(
            report.score,
            59,
        )

        self.assertIn(
            "EV is below strategy minimum",
            report.caution_reasons,
        )

    def test_market_drift_and_extreme_volatility_reduce_score(self):
        positive = self.build()

        negative = self.build(
            market_direction="drifting",
            market_volatility="extreme",
            clv_percent=-3.0,
        )

        self.assertLess(
            negative.score,
            positive.score,
        )

        self.assertIn(
            "The market is drifting against the selection.",
            negative.caution_reasons,
        )

    def test_missing_clv_is_neutral(self):
        report = self.build(
            clv_percent=None,
        )

        self.assertIsNone(
            report.clv_percent,
        )

        self.assertGreater(
            report.breakdown.market,
            0,
        )

    def test_high_portfolio_exposure_is_penalised(self):
        normal = self.build()

        exposed = self.build(
            portfolio_exposure_percent=15.0,
        )

        self.assertLess(
            exposed.score,
            normal.score,
        )

        self.assertIn(
            "Portfolio exposure exceeds the preferred limit.",
            exposed.caution_reasons,
        )

    def test_summary_is_json_ready(self):
        payload = decision_intelligence_summary(
            self.build(),
        )

        self.assertIsInstance(
            payload["breakdown"],
            dict,
        )

        self.assertIsInstance(
            payload["positive_reasons"],
            list,
        )

        self.assertIsInstance(
            payload["caution_reasons"],
            list,
        )


if __name__ == "__main__":
    unittest.main()