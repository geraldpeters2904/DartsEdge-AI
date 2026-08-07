import unittest
from types import SimpleNamespace

from app.services.prediction_centre_service import (
    _decision_intelligence_for_card,
)


class PredictionCentreDecisionIntelligenceTests(
    unittest.TestCase
):
    def test_builds_decision_payload(self):
        opportunity = {
            "probability": 62.0,
            "model_confidence": 78.0,
            "player_a_history_matches": 40,
            "player_b_history_matches": 35,
            "tournament": "MODUS",
        }

        assessment = SimpleNamespace(
            model_probability=62.0,
            expected_value_percent=10.0,
            edge_percent=8.0,
            decimal_odds=2.0,
            recommended_stake=20.0,
        )

        evidence = {
            "evidence_score": 82.0,
        }

        trust = SimpleNamespace(
            trust_score=74,
        )

        market = SimpleNamespace(
            movement_direction=(
                "shortening"
            ),
            volatility="low",
            clv_percent=None,
        )

        portfolio = {
            "exposure_percent": 2.0,
        }

        strategy = SimpleNamespace(
            name="Test",
            version=1,
            rules_json=(
                '{"mode":"paper",'
                '"decision_rules_enabled":true,'
                '"enforcement_mode":"shadow",'
                '"minimum_ev_percent":0,'
                '"minimum_edge_percent":2,'
                '"minimum_model_probability":50,'
                '"minimum_confidence_percent":50,'
                '"kelly_fraction":0.25,'
                '"maximum_portfolio_exposure_percent":25,'
                '"maximum_stake_percent":2,'
                '"minimum_sample_size":0,'
                '"maximum_decimal_odds":20,'
                '"allowed_markets":[],'
                '"allowed_competitions":[]}'
            ),
        )

        settings = SimpleNamespace(
            bankroll=1000.0,
        )

        payload = (
            _decision_intelligence_for_card(
                opportunity=opportunity,
                assessment=assessment,
                evidence=evidence,
                trust_report=trust,
                market_analysis=market,
                portfolio=portfolio,
                active_strategy_record=(
                    strategy
                ),
                settings=settings,
            )
        )

        self.assertIsNotNone(
            payload
        )

        self.assertGreaterEqual(
            payload["score"],
            60,
        )

        self.assertIn(
            payload[
                "recommendation"
            ],
            {
                "BET",
                "SMALL BET",
                "WATCH",
            },
        )

        self.assertEqual(
            payload[
                "strategy_status"
            ],
            "Qualifies",
        )

        self.assertIn(
            "market",
            payload[
                "breakdown"
            ],
        )

    def test_missing_assessment_is_not_scored(self):
        payload = (
            _decision_intelligence_for_card(
                opportunity={
                    "probability": 60.0,
                },
                assessment=None,
                evidence=None,
                trust_report=None,
                market_analysis=None,
                portfolio={},
                active_strategy_record=(
                    SimpleNamespace()
                ),
                settings=(
                    SimpleNamespace(
                        bankroll=1000
                    )
                ),
            )
        )

        self.assertIsNone(
            payload
        )


if __name__ == "__main__":
    unittest.main()
