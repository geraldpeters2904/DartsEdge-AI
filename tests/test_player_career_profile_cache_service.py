import unittest
from datetime import date

from app.models.match import Match
from app.models.player import Player
from app.models.player_career_profile import (
    PlayerCareerProfile,
)
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.player_career_profile_cache_service import (
    PlayerCareerProfileCacheService,
)
from app.services.player_profile_service import (
    get_player_profile,
)
from tests.helpers.database import create_test_session


class PlayerCareerProfileCacheServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()
        self.service = PlayerCareerProfileCacheService()

    def tearDown(self):
        self.db.close()

    def seed(self):
        player = Player(
            name="Jeff Smith",
            elo=1510,
        )
        opponent = Player(
            name="Jack Smith",
            elo=1490,
        )
        self.db.add_all([player, opponent])
        self.db.flush()

        match_one = Match(
            date=date(2026, 8, 1),
            status="completed",
            player_a=player.name,
            player_b=opponent.name,
            winner=player.name,
            score="4-2",
        )
        match_two = Match(
            date=date(2026, 8, 2),
            status="completed",
            player_a=opponent.name,
            player_b=player.name,
            winner=opponent.name,
            score="4-3",
        )
        self.db.add_all([match_one, match_two])
        self.db.flush()

        self.db.add_all([
            PlayerMatchPerformance(
                match_id=match_one.id,
                player_id=player.id,
                opponent_id=opponent.id,
                competition_code="MODUS",
                won_match=True,
                legs_won=4,
                legs_lost=2,
                three_dart_average=92.0,
                first_nine_average=99.0,
                scores_100_plus=8,
                scores_140_plus=4,
                scores_180=2,
                checkout_attempts=10,
                checkouts_completed=4,
                checkout_percentage=40.0,
                highest_checkout=121,
                source_provider="modus-official",
            ),
            PlayerMatchPerformance(
                match_id=match_two.id,
                player_id=player.id,
                opponent_id=opponent.id,
                competition_code="MODUS",
                won_match=False,
                legs_won=3,
                legs_lost=4,
                three_dart_average=88.0,
                first_nine_average=95.0,
                scores_100_plus=6,
                scores_140_plus=3,
                scores_180=1,
                checkout_attempts=8,
                checkouts_completed=3,
                checkout_percentage=37.5,
                highest_checkout=96,
                source_provider="modus-official",
            ),
        ])
        self.db.commit()

        return player

    def test_refreshes_materialised_career_profile(self):
        player = self.seed()

        profile = self.service.refresh_player(
            self.db,
            player_id=player.id,
        )

        self.assertEqual(profile.matches_played, 2)
        self.assertEqual(profile.wins, 1)
        self.assertEqual(profile.losses, 1)
        self.assertEqual(profile.win_percentage, 50.0)
        self.assertEqual(profile.legs_won, 7)
        self.assertEqual(profile.legs_lost, 6)
        self.assertEqual(profile.leg_difference, 1)
        self.assertEqual(
            profile.average_three_dart_average,
            90.0,
        )
        self.assertEqual(
            profile.average_first_nine_average,
            97.0,
        )
        self.assertEqual(profile.scores_180, 3)
        self.assertEqual(profile.maximums_per_match, 1.5)
        self.assertEqual(profile.checkout_attempts, 18)
        self.assertEqual(profile.checkouts_completed, 7)
        self.assertEqual(
            profile.calculated_checkout_percentage,
            38.889,
        )
        self.assertEqual(profile.highest_checkout, 121)
        self.assertEqual(
            self.service.recent_form(profile),
            ["L", "W"],
        )
        self.assertEqual(
            profile.first_match_date,
            date(2026, 8, 1),
        )
        self.assertEqual(
            profile.latest_match_date,
            date(2026, 8, 2),
        )

    def test_refresh_is_an_upsert(self):
        player = self.seed()

        first = self.service.refresh_player(
            self.db,
            player_id=player.id,
        )
        second = self.service.refresh_player(
            self.db,
            player_id=player.id,
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            self.db.query(PlayerCareerProfile).count(),
            1,
        )

    def test_refresh_all_only_profiles_players_with_performances(self):
        player = self.seed()
        self.db.add(Player(name="No Data Player"))
        self.db.commit()

        profiles = self.service.refresh_all(self.db)

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].player_id, player.id)

    def test_missing_player_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "does not exist",
        ):
            self.service.refresh_player(
                self.db,
                player_id=9999,
            )

    def test_compatibility_player_profile_uses_cache(self):
        self.seed()

        profile = get_player_profile(
            self.db,
            "Jeff Smith",
        )

        self.assertEqual(profile["matches"], 2)
        self.assertEqual(profile["wins"], 1)
        self.assertEqual(profile["losses"], 1)
        self.assertEqual(profile["win_pct"], 50.0)
        self.assertEqual(profile["average"], 90.0)
        self.assertEqual(
            profile["checkout"],
            38.889,
        )
        self.assertEqual(profile["scores_180"], 3)
        self.assertEqual(
            profile["recent_form"],
            ["L", "W"],
        )
        self.assertIn("dartsedge_rating", profile)


if __name__ == "__main__":
    unittest.main()
