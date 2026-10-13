import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.paper_trade import PaperTrade
from app.services.equity_service import get_equity_curve


class EquityServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_trade(self, status, profit_loss, settled_at):
        trade = PaperTrade(
            market="Match Winner",
            selection="Player A",
            odds=2.0,
            stake=10.0,
            status=status,
            profit_loss=profit_loss,
            settled_at=settled_at,
        )
        self.db.add(trade)
        self.db.commit()
        return trade

    def test_equity_curve_follows_settlement_order(self):
        now = datetime(2026, 10, 12, 12, 0)

        first_created = self.add_trade(
            "WON", 20.0, now + timedelta(hours=2)
        )
        second_created = self.add_trade(
            "LOST", -10.0, now
        )

        curve = get_equity_curve(self.db, starting_bankroll=1000.0)

        self.assertEqual(
            [row["trade"] for row in curve],
            [second_created.id, first_created.id],
        )
        self.assertEqual(
            [row["bankroll"] for row in curve],
            [990.0, 1010.0],
        )

    def test_equal_settlement_times_use_trade_id(self):
        settled_at = datetime(2026, 10, 12, 12, 0)

        first = self.add_trade("WON", 10.0, settled_at)
        second = self.add_trade("LOST", -5.0, settled_at)

        curve = get_equity_curve(self.db, starting_bankroll=1000.0)

        self.assertEqual(
            [row["trade"] for row in curve],
            [first.id, second.id],
        )

    def test_legacy_missing_settlement_time_is_supported(self):
        legacy = self.add_trade("WON", 10.0, None)
        recent = self.add_trade(
            "LOST", -5.0, datetime(2026, 10, 12, 12, 0)
        )

        curve = get_equity_curve(self.db, starting_bankroll=1000.0)

        self.assertEqual(len(curve), 2)
        self.assertEqual(
            {row["trade"] for row in curve},
            {legacy.id, recent.id},
        )
        self.assertEqual(curve[-1]["bankroll"], 1005.0)

    def test_open_trades_do_not_affect_realised_equity(self):
        self.add_trade("OPEN", None, None)
        self.add_trade(
            "WON", 10.0, datetime(2026, 10, 12, 12, 0)
        )

        curve = get_equity_curve(self.db, starting_bankroll=1000.0)

        self.assertEqual(len(curve), 1)
        self.assertEqual(curve[0]["bankroll"], 1010.0)


    def test_zero_stake_settled_trades_are_excluded(self):
        settled_at = datetime(2026, 10, 12, 12, 0)

        winner = self.add_trade("WON", 10.0, settled_at)
        rejected = self.add_trade(
            "WON", 0.0, settled_at + timedelta(minutes=1)
        )
        loser = self.add_trade(
            "LOST", -10.0, settled_at + timedelta(minutes=2)
        )

        rejected.stake = 0.0
        self.db.commit()

        curve = get_equity_curve(self.db, starting_bankroll=1000.0)

        self.assertEqual(
            [row["trade"] for row in curve],
            [winner.id, loser.id],
        )
        self.assertEqual(
            [row["bankroll"] for row in curve],
            [1010.0, 1000.0],
        )


if __name__ == "__main__":
    unittest.main()
