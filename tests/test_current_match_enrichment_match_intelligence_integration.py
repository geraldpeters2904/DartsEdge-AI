import unittest
from datetime import date

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.current_match_enrichment_profile_refresh_service import (
    CurrentMatchEnrichmentProfileRefreshService,
)
from app.services.match_intelligence_workspace_service import (
    build_match_intelligence,
)
from tests.helpers.database import create_test_session


class CurrentMatchEnrichmentMatchIntelligenceIntegrationTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()

        self.player_a = Player(
            name="Player A",
            elo=1550.0,
            average=0.0,
            checkout=0.0,
        )
        self.player_b = Player(
            name="Player B",
            elo=1480.0,
            average=0.0,
            checkout=0.0,
        )

        self.db.add_all(
            [
                self.player_a,
                self.player_b,
            ]
        )
        self.db.flush()

        completed = Match(
            date=date(2026, 8, 9),
            tournament="MODUS Super Series",
            stage="Group A",
            status="completed",
            player_a=self.player_a.name,
            player_b=self.player_b.name,
            winner=self.player_a.name,
            score="4-2",
        )

        self.db.add(completed)
        self.db.flush()

        self.completed_match_id = int(
            completed.id
        )

        self.db.add_all(
            [
                PlayerMatchPerformance(
                    match_id=completed.id,
                    player_id=self.player_a.id,
                    opponent_id=self.player_b.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-player-a"
                    ),
                    won_match=True,
                    legs_won=4,
                    legs_lost=2,
                    three_dart_average=96.0,
                    first_nine_average=103.0,
                    scores_100_plus=10,
                    scores_140_plus=6,
                    scores_180=3,
                    checkout_attempts=8,
                    checkouts_completed=4,
                    checkout_percentage=50.0,
                    highest_checkout=121,
                    source_provider="modus-official",
                    source_external_id=(
                        "modus:statistics:19001:"
                        "modus-player-player-a"
                    ),
                    source_confidence="verified",
                ),
                PlayerMatchPerformance(
                    match_id=completed.id,
                    player_id=self.player_b.id,
                    opponent_id=self.player_a.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-player-b"
                    ),
                    won_match=False,
                    legs_won=2,
                    legs_lost=4,
                    three_dart_average=89.0,
                    first_nine_average=95.0,
                    scores_100_plus=8,
                    scores_140_plus=4,
                    scores_180=1,
                    checkout_attempts=6,
                    checkouts_completed=2,
                    checkout_percentage=33.333,
                    highest_checkout=96,
                    source_provider="modus-official",
                    source_external_id=(
                        "modus:statistics:19001:"
                        "modus-player-player-b"
                    ),
                    source_confidence="verified",
                ),
            ]
        )

        upcoming = Match(
            date=date(2026, 8, 10),
            tournament="MODUS Super Series",
            stage="Group A",
            status="scheduled",
            player_a=self.player_a.name,
            player_b=self.player_b.name,
        )

        self.db.add(upcoming)
        self.db.commit()

        self.upcoming_match_id = int(
            upcoming.id
        )

    def tearDown(self):
        self.db.close()

    def test_refreshed_enrichment_is_visible_to_match_intelligence(self):
        refresh = (
            CurrentMatchEnrichmentProfileRefreshService()
        )

        result = refresh.refresh(
            self.db,
            internal_match_id=(
                self.completed_match_id
            ),
        )

        self.assertEqual(
            result.refreshed_count,
            2,
        )

        intelligence = (
            build_match_intelligence(
                self.db,
                self.upcoming_match_id,
            )
        )

        self.assertIsNotNone(
            intelligence
        )

        profile_a = intelligence[
            "profile_a"
        ]
        profile_b = intelligence[
            "profile_b"
        ]

        self.assertEqual(
            profile_a["matches"],
            1,
        )
        self.assertEqual(
            profile_b["matches"],
            1,
        )

        self.assertEqual(
            profile_a["wins"],
            1,
        )
        self.assertEqual(
            profile_b["wins"],
            0,
        )

        self.assertEqual(
            profile_a["average"],
            96.0,
        )
        self.assertEqual(
            profile_b["average"],
            89.0,
        )

        self.assertEqual(
            profile_a["scores_180"],
            3,
        )
        self.assertEqual(
            profile_b["scores_180"],
            1,
        )

        self.assertEqual(
            profile_a["checkout"],
            50.0,
        )

        self.assertEqual(
            profile_a["recent_form"],
            ["W"],
        )
        self.assertEqual(
            profile_b["recent_form"],
            ["L"],
        )


if __name__ == "__main__":
    unittest.main()
