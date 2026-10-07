import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.models.strategy_profile import StrategyProfile
from app.services.strategy_service import (
    seed_default_strategies,
    strategy_rules,
    update_strategy,
)
from tests.helpers.database import create_test_session


class TradingOpportunitiesDecisionEngineTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()
        self.client = TestClient(app)

        self.prediction = Prediction(
            player_a="Trading Alpha",
            player_b="Trading Beta",
            predicted_winner="Trading Alpha",
            win_prob_a=65.0,
            win_prob_b=35.0,
            confidence=65,
            rating_a=1600.0,
            rating_b=1500.0,
            first_180_a=55.0,
            first_180_b=45.0,
        )
        self.db.add(self.prediction)
        self.db.commit()
        self.db.refresh(self.prediction)

        self.session_patch = patch(
            "app.routes.paper_trades.SessionLocal",
            return_value=self.db,
        )
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.db.close()

    def test_entered_odds_recalculate_value_and_kelly(self):
        seed_default_strategies(self.db)

        base_payload = {
            "prediction_id": self.prediction.id,
            "market": "match_winner",
            "selection": "Trading Alpha",
            "model_probability": 65.0,
            "confidence_percent": 80.0,
            "sample_size": 50,
            "competition": "MODUS Super Series",
            "bookmaker": "Trading Opportunities",
        }

        lower = self.client.post(
            "/api/trading-opportunities/evaluate",
            json={**base_payload, "odds": 1.70},
        )
        higher = self.client.post(
            "/api/trading-opportunities/evaluate",
            json={**base_payload, "odds": 2.00},
        )

        self.assertEqual(lower.status_code, 200)
        self.assertEqual(higher.status_code, 200)

        lower_payload = lower.json()
        higher_payload = higher.json()

        self.assertGreater(
            higher_payload["expected_value_percent"],
            lower_payload["expected_value_percent"],
        )
        self.assertGreater(
            higher_payload["raw_kelly_stake"],
            lower_payload["raw_kelly_stake"],
        )

    def test_active_rejection_zeroes_effective_stake_not_raw_kelly(self):
        seed_default_strategies(self.db)
        active = (
            self.db.query(StrategyProfile)
            .filter_by(is_active=True)
            .first()
        )
        rules = strategy_rules(active)
        rules["enforcement_mode"] = "active"
        rules["minimum_model_probability"] = 70.0
        update_strategy(
            self.db,
            active.id,
            name=active.name,
            description=active.description,
            rules=rules,
        )

        response = self.client.post(
            "/api/trading-opportunities/evaluate",
            json={
                "prediction_id": self.prediction.id,
                "market": "match_winner",
                "selection": "Trading Alpha",
                "odds": 2.0,
                "model_probability": 65.0,
                "confidence_percent": 80.0,
                "sample_size": 50,
                "competition": "MODUS Super Series",
                "bookmaker": "Trading Opportunities",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertGreater(payload["raw_kelly_stake"], 0.0)
        self.assertTrue(payload["decision_engine"]["enforced"])
        self.assertEqual(
            payload["decision_engine"]["effective_decision"],
            "Reject",
        )
        self.assertEqual(
            payload["decision_engine"]["effective_stake"],
            0.0,
        )

    def test_shadow_mode_preserves_raw_kelly_as_effective_stake(self):
        seed_default_strategies(self.db)

        response = self.client.post(
            "/api/trading-opportunities/evaluate",
            json={
                "prediction_id": self.prediction.id,
                "market": "match_winner",
                "selection": "Trading Alpha",
                "odds": 2.0,
                "model_probability": 65.0,
                "confidence_percent": 80.0,
                "sample_size": 50,
                "competition": "MODUS Super Series",
                "bookmaker": "Trading Opportunities",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertGreater(payload["raw_kelly_stake"], 0.0)
        self.assertFalse(payload["decision_engine"]["enforced"])
        self.assertEqual(
            payload["decision_engine"]["effective_stake"],
            payload["raw_kelly_stake"],
        )

    def test_shadow_save_persists_effective_and_raw_stakes(self):
        seed_default_strategies(self.db)

        response = self.client.post(
            "/api/paper-trades",
            json={
                "prediction_id": self.prediction.id,
                "market": "Match Winner",
                "decision_market": "match_winner",
                "selection": "Trading Alpha",
                "odds": 2.0,
                "model_probability": 65.0,
                "confidence_percent": 80.0,
                "sample_size": 50,
                "competition": "MODUS Super Series",
                "bookmaker": "Trading Opportunities",
            },
        )

        self.assertEqual(response.status_code, 200)

        trade = self.db.query(PaperTrade).one()

        self.assertGreater(trade.suggested_stake, 0.0)
        self.assertEqual(
            trade.stake,
            trade.suggested_stake,
        )
        self.assertEqual(trade.model_probability, 65.0)
        self.assertGreater(trade.expected_value, 0.0)
        self.assertIsNotNone(trade.strategy_name)

    def test_active_rejection_save_persists_zero_effective_stake(self):
        seed_default_strategies(self.db)
        active = (
            self.db.query(StrategyProfile)
            .filter_by(is_active=True)
            .first()
        )
        rules = strategy_rules(active)
        rules["enforcement_mode"] = "active"
        rules["minimum_model_probability"] = 70.0
        update_strategy(
            self.db,
            active.id,
            name=active.name,
            description=active.description,
            rules=rules,
        )

        response = self.client.post(
            "/api/paper-trades",
            json={
                "prediction_id": self.prediction.id,
                "market": "Match Winner",
                "decision_market": "match_winner",
                "selection": "Trading Alpha",
                "odds": 2.0,
                "model_probability": 65.0,
                "confidence_percent": 80.0,
                "sample_size": 50,
                "competition": "MODUS Super Series",
                "bookmaker": "Trading Opportunities",
            },
        )

        self.assertEqual(response.status_code, 200)

        trade = self.db.query(PaperTrade).one()

        self.assertGreater(trade.suggested_stake, 0.0)
        self.assertEqual(trade.stake, 0.0)
        self.assertEqual(trade.model_probability, 65.0)
        self.assertGreater(trade.expected_value, 0.0)
        self.assertIsNotNone(trade.strategy_name)


if __name__ == "__main__":
    unittest.main()
