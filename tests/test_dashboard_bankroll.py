import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.settings import Settings
from app.services.dashboard_service import build_dashboard_data


class DashboardBankrollTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(Settings(bankroll=1234.0))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch(
        "app.services.dashboard_service.get_data_quality",
        return_value={"health_score": 100},
    )
    @patch(
        "app.services.dashboard_service.build_value_board",
        return_value=[],
    )
    def test_dashboard_uses_configured_bankroll(
        self,
        _value_board,
        _data_quality,
    ):
        result = build_dashboard_data(self.db)

        self.assertEqual(result["starting_bankroll"], 1234.0)
        self.assertEqual(result["current_bankroll"], 1234.0)
        self.assertEqual(result["equity_curve"], [])


    def test_void_trade_excluded_from_roi_turnover(self):
        from app.models.paper_trade import PaperTrade
        from app.services.paper_trade_service import get_portfolio_summary

        self.db.add_all([
            PaperTrade(
                market="Match Winner",
                selection="Player A",
                odds=2.0,
                stake=20.0,
                status="WON",
                profit_loss=20.0,
            ),
            PaperTrade(
                market="Match Winner",
                selection="Player B",
                odds=2.0,
                stake=100.0,
                status="VOID",
                profit_loss=0.0,
            ),
        ])
        self.db.commit()

        result = get_portfolio_summary(
            self.db,
            starting_bankroll=1234.0,
        )

        self.assertEqual(result["total_profit_loss"], 20.0)
        self.assertEqual(result["current_bankroll"], 1254.0)
        self.assertEqual(result["settled_stake"], 20.0)
        self.assertEqual(result["portfolio_roi"], 100.0)


if __name__ == "__main__":
    unittest.main()
