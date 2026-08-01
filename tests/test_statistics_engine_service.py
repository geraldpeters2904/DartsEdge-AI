import unittest
from datetime import date, datetime, timedelta

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.statistics_engine_service import StatisticsEngineService
from tests.helpers.database import create_test_session


class StatisticsEngineServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = StatisticsEngineService()

        self.player = Player(name="Alpha")
        self.opponent = Player(name="Bravo")
        self.db.add_all([self.player, self.opponent])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def add_performance(
        self,
        *,
        days_ago,
        won_match,
        competition_code="MODUS",
        legs_won=4,
        legs_lost=2,
        three_dart_average=None,
        first_nine_average=None,
        scores_100_plus=None,
        scores_140_plus=None,
        scores_180=None,
        checkout_attempts=None,
        checkouts_completed=None,
        checkout_percentage=None,
        highest_checkout=None,
    ):
        match = Match(
            date=date.today() - timedelta(days=days_ago),
            tournament="MODUS",
            status="completed",
            player_a="Alpha",
            player_b="Bravo",
            winner="Alpha" if won_match else "Bravo",
        )
        self.db.add(match)
        self.db.flush()

        performance = PlayerMatchPerformance(
            match_id=match.id,
            player_id=self.player.id,
            opponent_id=self.opponent.id,
            competition_code=competition_code,
            won_match=won_match,
            legs_won=legs_won,
            legs_lost=legs_lost,
            three_dart_average=three_dart_average,
            first_nine_average=first_nine_average,
            scores_100_plus=scores_100_plus,
            scores_140_plus=scores_140_plus,
            scores_180=scores_180,
            checkout_attempts=checkout_attempts,
            checkouts_completed=checkouts_completed,
            checkout_percentage=checkout_percentage,
            highest_checkout=highest_checkout,
            source_provider="test",
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        self.db.add(performance)
        self.db.commit()

    def test_builds_base_player_statistics(self):
        self.add_performance(
            days_ago=2,
            won_match=True,
            legs_won=4,
            legs_lost=1,
            three_dart_average=96.0,
            first_nine_average=102.0,
            scores_100_plus=8,
            scores_140_plus=4,
            scores_180=2,
            checkout_attempts=10,
            checkouts_completed=4,
            checkout_percentage=40.0,
            highest_checkout=121,
        )
        self.add_performance(
            days_ago=1,
            won_match=False,
            legs_won=2,
            legs_lost=4,
            three_dart_average=90.0,
            first_nine_average=96.0,
            scores_100_plus=6,
            scores_140_plus=3,
            scores_180=1,
            checkout_attempts=8,
            checkouts_completed=2,
            checkout_percentage=25.0,
            highest_checkout=84,
        )

        stats = self.service.build_player_statistics(
            self.db,
            self.player.id,
        )

        self.assertEqual(stats.matches_played, 2)
        self.assertEqual(stats.wins, 1)
        self.assertEqual(stats.losses, 1)
        self.assertEqual(stats.win_percentage, 50.0)

        self.assertEqual(stats.legs_won, 6)
        self.assertEqual(stats.legs_lost, 5)
        self.assertEqual(stats.leg_difference, 1)

        self.assertEqual(stats.average_three_dart_average, 93.0)
        self.assertEqual(stats.average_first_nine_average, 99.0)

        self.assertEqual(stats.scores_100_plus, 14)
        self.assertEqual(stats.scores_140_plus, 7)
        self.assertEqual(stats.scores_180, 3)
        self.assertEqual(stats.maximums_per_match, 1.5)

        self.assertEqual(stats.checkout_attempts, 18)
        self.assertEqual(stats.checkouts_completed, 6)
        self.assertEqual(
            stats.calculated_checkout_percentage,
            33.333,
        )
        self.assertEqual(
            stats.average_reported_checkout_percentage,
            32.5,
        )
        self.assertEqual(stats.highest_checkout, 121)

        self.assertEqual(stats.recent_form, ["L", "W"])

    def test_ignores_missing_optional_statistics(self):
        self.add_performance(
            days_ago=1,
            won_match=True,
            three_dart_average=None,
            first_nine_average=None,
            scores_100_plus=None,
            scores_140_plus=None,
            scores_180=None,
            checkout_attempts=None,
            checkouts_completed=None,
            checkout_percentage=None,
            highest_checkout=None,
        )

        stats = self.service.build_player_statistics(
            self.db,
            self.player.id,
        )

        self.assertEqual(stats.matches_played, 1)
        self.assertEqual(stats.scores_180, 0)
        self.assertEqual(stats.maximums_per_match, 0.0)
        self.assertIsNone(stats.average_three_dart_average)
        self.assertIsNone(stats.average_first_nine_average)
        self.assertIsNone(stats.calculated_checkout_percentage)
        self.assertIsNone(
            stats.average_reported_checkout_percentage
        )
        self.assertIsNone(stats.highest_checkout)

    def test_filters_by_competition(self):
        self.add_performance(
            days_ago=2,
            won_match=True,
            competition_code="MODUS",
        )
        self.add_performance(
            days_ago=1,
            won_match=False,
            competition_code="PDC",
        )

        stats = self.service.build_player_statistics(
            self.db,
            self.player.id,
            competition_code="MODUS",
        )

        self.assertEqual(stats.matches_played, 1)
        self.assertEqual(stats.wins, 1)
        self.assertEqual(stats.losses, 0)
        self.assertEqual(stats.competition_code, "MODUS")

    def test_recent_form_respects_limit(self):
        results = [True, False, True, True, False]

        for days_ago, won_match in enumerate(
            reversed(results),
            start=1,
        ):
            self.add_performance(
                days_ago=days_ago,
                won_match=won_match,
            )

        stats = self.service.build_player_statistics(
            self.db,
            self.player.id,
            recent_limit=3,
        )

        self.assertEqual(len(stats.recent_form), 3)


if __name__ == "__main__":
    unittest.main()
