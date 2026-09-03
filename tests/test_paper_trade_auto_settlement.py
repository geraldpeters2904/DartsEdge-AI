import unittest

from datetime import date

from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.models.prediction import Prediction
from app.services.paper_trade_service import (
    settle_open_first_180_trades_for_fixture,
    settle_open_match_winner_trades_for_fixture,
    settle_open_most_180s_trades_for_fixture,
    settle_open_trades_for_fixture,
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

    def add_most_180s_performances(
        self,
        *,
        player_a_180s=2,
        player_b_180s=1,
        include_player_a=True,
        include_player_b=True,
    ):
        player_a = Player(name=self.match.player_a)
        player_b = Player(name=self.match.player_b)
        self.db.add_all([player_a, player_b])
        self.db.flush()

        if include_player_a:
            self.db.add(
                PlayerMatchPerformance(
                    match_id=self.match.id,
                    player_id=player_a.id,
                    opponent_id=player_b.id,
                    scores_180=player_a_180s,
                    source_provider="test",
                )
            )

        if include_player_b:
            self.db.add(
                PlayerMatchPerformance(
                    match_id=self.match.id,
                    player_id=player_b.id,
                    opponent_id=player_a.id,
                    scores_180=player_b_180s,
                    source_provider="test",
                )
            )

        self.db.flush()

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


    def test_winning_first_180_trade_is_settled(self):
        self.match.first_180_player = "Player B"
        trade = self.add_trade(
            market="First 180",
            selection="Player B",
            stake=10,
            odds=2.5,
        )
        self.db.flush()

        settled = settle_open_first_180_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual([row.id for row in settled], [trade.id])
        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 15.0)
        self.assertIsNotNone(trade.settled_at)

    def test_losing_first_180_trade_is_settled(self):
        self.match.first_180_player = "Player B"
        trade = self.add_trade(
            market="First 180",
            selection="Player A",
            stake=10,
            odds=2.5,
        )
        self.db.flush()

        settle_open_first_180_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(trade.status, "LOST")
        self.assertEqual(trade.profit_loss, -10.0)

    def test_first_180_trade_without_result_data_stays_open(self):
        trade = self.add_trade(
            market="First 180",
            selection="Player A",
        )

        settled = settle_open_first_180_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_invalid_first_180_result_player_stays_open(self):
        self.match.first_180_player = "Unknown Player"
        trade = self.add_trade(
            market="First 180",
            selection="Player A",
        )
        self.db.flush()

        settled = settle_open_first_180_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_invalid_first_180_selection_stays_open(self):
        self.match.first_180_player = "Player B"
        trade = self.add_trade(
            market="First 180",
            selection="Unknown Player",
        )
        self.db.flush()

        settled = settle_open_first_180_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)


    def test_most_180s_player_a_win_is_settled(self):
        self.add_most_180s_performances(
            player_a_180s=3,
            player_b_180s=1,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
            stake=10,
            odds=2.5,
        )

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual([row.id for row in settled], [trade.id])
        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 15.0)
        self.assertIsNotNone(trade.settled_at)

    def test_most_180s_player_b_win_is_settled(self):
        self.add_most_180s_performances(
            player_a_180s=1,
            player_b_180s=3,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
        )

        settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(trade.status, "LOST")
        self.assertEqual(trade.profit_loss, -10.0)

    def test_most_180s_draw_is_settled(self):
        self.add_most_180s_performances(
            player_a_180s=2,
            player_b_180s=2,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Draw",
            stake=10,
            odds=3.0,
        )

        settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 20.0)

    def test_most_180s_missing_player_performance_stays_open(self):
        self.add_most_180s_performances(
            include_player_b=False,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
        )

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_most_180s_null_count_stays_open(self):
        self.add_most_180s_performances(
            player_a_180s=None,
            player_b_180s=1,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Player B",
        )

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_invalid_most_180s_selection_stays_open(self):
        self.add_most_180s_performances()
        trade = self.add_trade(
            market="Most 180s",
            selection="Unknown Player",
        )

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")
        self.assertIsNone(trade.profit_loss)
        self.assertIsNone(trade.settled_at)

    def test_incomplete_fixture_does_not_settle_most_180s(self):
        self.add_most_180s_performances()
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
        )
        self.match.status = "scheduled"
        self.db.flush()

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "OPEN")

    def test_already_settled_most_180s_trade_is_untouched(self):
        self.add_most_180s_performances()
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
            status="WON",
        )
        trade.profit_loss = 10.0
        self.db.flush()

        settled = settle_open_most_180s_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(settled, [])
        self.assertEqual(trade.status, "WON")
        self.assertEqual(trade.profit_loss, 10.0)

    def test_most_180s_settlement_participates_in_caller_transaction(self):
        self.add_most_180s_performances(
            player_a_180s=3,
            player_b_180s=1,
        )
        trade = self.add_trade(
            market="Most 180s",
            selection="Player A",
            stake=10,
            odds=2.5,
        )
        trade_id = trade.id
        self.db.commit()

        settle_open_most_180s_trades_for_fixture(
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

    def test_fixture_settlement_handles_match_winner_and_first_180(self):
        self.match.first_180_player = "Player B"
        match_winner = self.add_trade(
            market="Match Winner",
            selection="Player A",
            stake=10,
            odds=2.5,
        )
        first_180 = self.add_trade(
            market="First 180",
            selection="Player B",
            stake=10,
            odds=2.0,
        )
        unsupported = self.add_trade(
            market="Most 180s",
            selection="Player A",
        )
        self.db.flush()

        settled = settle_open_trades_for_fixture(
            self.db,
            self.match.id,
        )

        self.assertEqual(
            {row.id for row in settled},
            {match_winner.id, first_180.id},
        )
        self.assertEqual(match_winner.status, "WON")
        self.assertEqual(match_winner.profit_loss, 15.0)
        self.assertEqual(first_180.status, "WON")
        self.assertEqual(first_180.profit_loss, 10.0)
        self.assertEqual(unsupported.status, "OPEN")
        self.assertIsNone(unsupported.profit_loss)

    def test_first_180_settlement_participates_in_caller_transaction(self):
        self.match.first_180_player = "Player B"
        trade = self.add_trade(
            market="First 180",
            selection="Player B",
            stake=10,
            odds=2.5,
        )
        trade_id = trade.id
        self.db.commit()

        settle_open_first_180_trades_for_fixture(
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


if __name__ == "__main__":
    unittest.main()
