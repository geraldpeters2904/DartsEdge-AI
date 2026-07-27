import unittest

from sqlalchemy.exc import IntegrityError

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from tests.helpers.database import create_test_session


class PlayerMatchPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        self.player_a = Player(name="Player A")
        self.player_b = Player(name="Player B")

        self.db.add_all([self.player_a, self.player_b])
        self.db.flush()

        self.match = Match(
            tournament="MODUS Super Series",
            status="completed",
            player_a="Player A",
            player_b="Player B",
            winner="Player A",
            score="4-2",
        )

        self.db.add(self.match)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def build_performance(self, **overrides):
        values = {
            "match_id": self.match.id,
            "player_id": self.player_a.id,
            "opponent_id": self.player_b.id,
            "competition_code": "MODUS",
            "player_external_id": "player-a",
            "won_match": True,
            "legs_won": 4,
            "legs_lost": 2,
            "three_dart_average": 94.25,
            "first_nine_average": 101.50,
            "scores_100_plus": 12,
            "scores_140_plus": 6,
            "scores_180": 2,
            "checkout_attempts": 10,
            "checkouts_completed": 4,
            "checkout_percentage": 40.0,
            "highest_checkout": 121,
            "match_duration_seconds": 1680,
            "source_provider": "manual-research",
            "source_external_id": "match-1:player-a",
            "source_confidence": "reported",
        }
        values.update(overrides)
        return PlayerMatchPerformance(**values)

    def test_performance_record_is_stored(self):
        performance = self.build_performance()

        self.db.add(performance)
        self.db.commit()

        stored = self.db.query(PlayerMatchPerformance).one()

        self.assertEqual(stored.player_id, self.player_a.id)
        self.assertEqual(stored.opponent_id, self.player_b.id)
        self.assertEqual(stored.three_dart_average, 94.25)
        self.assertEqual(stored.scores_180, 2)
        self.assertTrue(stored.won_match)

    def test_unknown_values_remain_null(self):
        performance = self.build_performance(
            scores_180=None,
            checkout_percentage=None,
            highest_checkout=None,
        )

        self.db.add(performance)
        self.db.commit()

        stored = self.db.query(PlayerMatchPerformance).one()

        self.assertIsNone(stored.scores_180)
        self.assertIsNone(stored.checkout_percentage)
        self.assertIsNone(stored.highest_checkout)

    def test_explicit_zero_is_preserved(self):
        performance = self.build_performance(
            scores_180=0,
            checkout_attempts=0,
            checkouts_completed=0,
        )

        self.db.add(performance)
        self.db.commit()

        stored = self.db.query(PlayerMatchPerformance).one()

        self.assertEqual(stored.scores_180, 0)
        self.assertEqual(stored.checkout_attempts, 0)
        self.assertEqual(stored.checkouts_completed, 0)

    def test_player_and_match_pair_must_be_unique(self):
        self.db.add(self.build_performance())
        self.db.commit()

        self.db.add(
            self.build_performance(
                three_dart_average=99.0,
            )
        )

        with self.assertRaises(IntegrityError):
            self.db.commit()

        self.db.rollback()

    def test_two_players_can_have_performances_for_same_match(self):
        self.db.add(self.build_performance())

        self.db.add(
            self.build_performance(
                player_id=self.player_b.id,
                opponent_id=self.player_a.id,
                player_external_id="player-b",
                won_match=False,
                legs_won=2,
                legs_lost=4,
                three_dart_average=90.10,
                scores_180=1,
                source_external_id="match-1:player-b",
            )
        )

        self.db.commit()

        self.assertEqual(
            self.db.query(PlayerMatchPerformance).count(),
            2,
        )


if __name__ == "__main__":
    unittest.main()