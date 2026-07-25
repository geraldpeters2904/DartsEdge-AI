import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.models.settings import Settings
from app.services.ai_coach_service import build_ai_coach_data


class AiCoachServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Settings(bankroll=1000, max_daily_risk=10, kelly_fraction=0.5))
        self.prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
            win_prob_a=65,
            win_prob_b=35,
            confidence=65,
        )
        self.db.add(self.prediction)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_open_trade(self, stake):
        self.db.add(PaperTrade(
            prediction_id=self.prediction.id,
            market="Match Winner",
            selection="Player A",
            bookmaker="Test Book",
            odds=2.0,
            stake=stake,
            status="OPEN",
            profit_loss=None,
            settled_at=None,
            created_at=datetime.utcnow(),
        ))
        self.db.commit()

    @patch("app.services.ai_coach_service.build_ranked_opportunities", return_value=[])
    @patch("app.services.ai_coach_service.build_dashboard_data")
    def test_payload_contains_daily_briefing_sections(self, dashboard_mock, _opportunities_mock):
        dashboard_mock.return_value = {
            "database_health": 90,
            "results_awaiting": [],
            "prediction_count": 30,
        }
        result = build_ai_coach_data(self.db)
        self.assertIn("primary", result)
        self.assertIn("recommendations", result)
        self.assertGreaterEqual(result["recommendation_count"], 2)

    @patch("app.services.ai_coach_service.build_ranked_opportunities", return_value=[])
    @patch("app.services.ai_coach_service.build_dashboard_data")
    def test_risk_limit_breach_becomes_top_priority(self, dashboard_mock, _opportunities_mock):
        dashboard_mock.return_value = {
            "database_health": 90,
            "results_awaiting": [],
            "prediction_count": 30,
        }
        self.add_open_trade(120)
        result = build_ai_coach_data(self.db)
        self.assertEqual(result["primary"]["tone"], "risk")
        self.assertEqual(result["primary"]["title"], "Pause new positions")

    @patch("app.services.ai_coach_service.build_dashboard_data")
    @patch("app.services.ai_coach_service.build_ranked_opportunities")
    def test_unpriced_signal_is_not_called_confirmed_value(self, opportunities_mock, dashboard_mock):
        dashboard_mock.return_value = {
            "database_health": 90,
            "results_awaiting": [],
            "prediction_count": 30,
        }
        opportunities_mock.return_value = [{
            "selection": "Player A",
            "probability": 70.0,
            "market_odds": None,
            "minimum_odds": 1.55,
            "fair_odds": 1.43,
            "is_value_confirmed": False,
        }]
        result = build_ai_coach_data(self.db)
        titles = [item["title"] for item in result["recommendations"]]
        self.assertIn("Check odds for Player A", titles)
        self.assertEqual(result["confirmed_value_count"], 0)

    @patch("app.services.ai_coach_service.build_dashboard_data")
    @patch("app.services.ai_coach_service.build_ranked_opportunities")
    def test_confirmed_value_is_reported(self, opportunities_mock, dashboard_mock):
        dashboard_mock.return_value = {
            "database_health": 90,
            "results_awaiting": [],
            "prediction_count": 30,
        }
        opportunities_mock.return_value = [{
            "selection": "Player A",
            "probability": 70.0,
            "market_odds": 1.70,
            "edge_percent": 11.18,
            "is_value_confirmed": True,
        }]
        result = build_ai_coach_data(self.db)
        self.assertEqual(result["confirmed_value_count"], 1)
        self.assertTrue(any("Confirmed value" in item["title"] for item in result["recommendations"]))

    @patch("app.services.ai_coach_service.build_ranked_opportunities", return_value=[])
    @patch("app.services.ai_coach_service.build_dashboard_data")
    def test_low_database_health_creates_urgent_advice(self, dashboard_mock, _opportunities_mock):
        dashboard_mock.return_value = {
            "database_health": 55,
            "results_awaiting": [],
            "prediction_count": 30,
        }
        result = build_ai_coach_data(self.db)
        self.assertTrue(any(item["category"] == "Data quality" and item["tone"] == "risk" for item in result["recommendations"]))


if __name__ == "__main__":
    unittest.main()
