import unittest

from datetime import date

from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.services.paper_trade_service import (
    settle_open_match_winner_trades_for_fixture,
)
from tests.helpers.database import create_test_session


class PaperTradeAutoSettlementTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        self.match = Match(
            date=date(2026, 9, 2),
            tournament="MODUS",
            status="completed",
            player_a="Player A",
            player_b="Player B",
            winner="Player A",
            score="4-2",
        )
        self.db.add(self.match)
        self.db.flush()

        self.prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
            win_prob_a=0.60,
            win_prob_b=0.40,
            confidence=2,
            rating_a=0,
            rating_b=0,
            first_180_a=0,
            first_180_b=0,
        )
        self.db.add(self.prediction)
        self.db.flush()

    def tearDown(self):
        self.db.close()

    def add_trade(
        self,
        *,
        selection="Player A",
        market="Match Winner",
        status="OPEN",
        fixture_id=None,
        stake=10.0,
        odds=2.0,
    ):
        trade = PaperTrade(
            prediction_id=self.prediction.id,
            fixture_id=(
                self.match.id
                if fixture_id is None
                else fixture_id
            ),
            market=market,
            selection=selection,
            bookmaker="Test",
            odds=odds,
            stake=stake,
            status=status,
        )
        self.db.add(trade)
        self.db.flush()
        return trade

    def test_winning_match_winner_trade_is_settled(self):
        trade = self.add_trade(
            selection="Player A",
            stake=10,
            odds=2.5,
        )

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual([row.id for row in settled], [trade.id])
        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 15.0)
        self.assertIsNotNone(trade.settled_at)

    def test_losing_match_winner_trade_is_settled(self):
        trade = self.add_trade(
            selection="Player B",
            stake=10,
            odds=2.5,
        )

        settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(trade.status, "LOST")
        self.assertEqual(trade.profit_loss, -10.0)

    def test_unsupported_market_is_left_open(self):
        trade = self.add_trade(
            market="Most 180s",
        )

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_trade_without_fixture_link_is_untouched(self):
        trade = self.add_trade()
        trade.fixture_id = None
        self.db.flush()

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")

    def test_already_settled_trade_is_untouched(self):
        trade = self.add_trade(status="WON")
        trade.profit_loss = 10.0
        self.db.flush()

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 10.0)

    def test_invalid_match_winner_selection_is_left_open(self):
        trade = self.add_trade(
            selection="Unknown Player",
        )

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_settlement_participates_in_caller_transaction(self):
        trade = self.add_trade(
            selection="Player A",
            stake=10,
            odds=2.5,
        )
        trade_id = trade.id

        self.db.commit()

        settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 15.0)

        self.db.rollback()
        self.db.expire_all()

        restored = self.db.get(PaperTrade, trade_id)

        self.assertEqual(restored.status, "OPEN")
        self.assertIsNone(restored.profit_loss)
        self.assertIsNone(restored.settled_at)

    def test_incomplete_fixture_does_not_settle(self):
        trade = self.add_trade()
        self.match.status = "scheduled"
        self.db.flush()

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")

    def test_completed_fixture_without_winner_does_not_settle(self):
        trade = self.add_trade()
        self.match.winner = None
        self.db.flush()

        settled = settle_open_match_winner_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")


if __name__ == "__main__":
    unittest.main()
