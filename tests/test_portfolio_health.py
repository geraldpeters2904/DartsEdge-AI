import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.models.settings import Settings
from app.services.portfolio_health_service import build_portfolio_health


class PortfolioHealthServiceTests(unittest.TestCase):
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

    def add_trade(self, status, stake, odds=2.0, profit_loss=None, selection="Player A", market="Match Winner"):
        trade = PaperTrade(
            prediction_id=self.prediction.id,
            market=market,
            selection=selection,
            bookmaker="Test Book",
            odds=odds,
            stake=stake,
            status=status,
            profit_loss=profit_loss,
            settled_at=datetime.utcnow() if status != "OPEN" else None,
        )
        self.db.add(trade)
        self.db.commit()
        return trade

    def test_empty_portfolio_uses_settings_bankroll(self):
        result = build_portfolio_health(self.db)
        self.assertEqual(result["current_bankroll"], 1000.0)
        self.assertEqual(result["available_bankroll"], 1000.0)
        self.assertEqual(result["health_score"], 100)
        self.assertEqual(result["risk_level"], "good")

    def test_open_exposure_reduces_available_bankroll(self):
        self.add_trade("OPEN", 50)
        result = build_portfolio_health(self.db)
        self.assertEqual(result["open_exposure"], 50.0)
        self.assertEqual(result["available_bankroll"], 950.0)
        self.assertEqual(result["exposure_percent"], 5.0)

    def test_settled_results_update_bankroll_roi_and_win_rate(self):
        self.add_trade("WON", 20, odds=2.0, profit_loss=20)
        self.add_trade("LOST", 10, odds=2.0, profit_loss=-10)
        result = build_portfolio_health(self.db)
        self.assertEqual(result["current_bankroll"], 1010.0)
        self.assertEqual(result["total_profit_loss"], 10.0)
        self.assertEqual(result["roi"], 33.33)
        self.assertEqual(result["win_rate"], 50.0)

    def test_risk_limit_breach_is_flagged(self):
        self.add_trade("OPEN", 120)
        result = build_portfolio_health(self.db)
        self.assertEqual(result["risk_level"], "risk")
        self.assertLess(result["health_score"], 80)
        self.assertEqual(result["coach"]["tone"], "risk")

    def test_exposure_is_grouped_by_player_and_market(self):
        self.add_trade("OPEN", 30, selection="Player A", market="Match Winner")
        self.add_trade("OPEN", 20, selection="Player A", market="Most 180s")
        result = build_portfolio_health(self.db)
        self.assertEqual(result["exposure_by_player"][0]["exposure"], 50.0)
        self.assertEqual(len(result["exposure_by_market"]), 2)


if __name__ == "__main__":
    unittest.main()
