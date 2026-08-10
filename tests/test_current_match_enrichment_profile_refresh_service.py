import unittest

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.current_match_enrichment_profile_refresh_service import (
    CurrentMatchEnrichmentProfileRefreshService,
)
from tests.helpers.database import create_test_session


class FakeProfileCacheService:
    def __init__(self):
        self.calls = []

    def refresh_players(
        self,
        db,
        *,
        player_ids,
    ):
        ids = tuple(player_ids)
        self.calls.append(
            (db, ids)
        )
        return [
            object()
            for _ in ids
        ]


class CurrentMatchEnrichmentProfileRefreshServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()

        player_a = Player(
            name="Player A",
            elo=1500.0,
            average=90.0,
            checkout=35.0,
        )
        player_b = Player(
            name="Player B",
            elo=1500.0,
            average=88.0,
            checkout=33.0,
        )

        self.db.add_all(
            [
                player_a,
                player_b,
            ]
        )
        self.db.flush()

        match = Match(
            player_a="Player A",
            player_b="Player B",
            status="completed",
        )

        self.db.add(match)
        self.db.flush()

        self.match_id = int(match.id)
        self.player_ids = (
            int(player_a.id),
            int(player_b.id),
        )

        self.db.add_all(
            [
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=player_a.id,
                    opponent_id=player_b.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-player-a"
                    ),
                    source_provider="modus-official",
                    source_external_id="stats-a",
                    source_confidence="verified",
                ),
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=player_b.id,
                    opponent_id=player_a.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-player-b"
                    ),
                    source_provider="modus-official",
                    source_external_id="stats-b",
                    source_confidence="verified",
                ),
            ]
        )

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_refreshes_exactly_two_affected_players(self):
        cache = FakeProfileCacheService()

        service = (
            CurrentMatchEnrichmentProfileRefreshService(
                profile_cache_service=cache,
            )
        )

        result = service.refresh(
            self.db,
            internal_match_id=self.match_id,
        )

        self.assertEqual(
            result.status,
            "refreshed",
        )
        self.assertEqual(
            result.refreshed_count,
            2,
        )
        self.assertEqual(
            result.player_ids,
            tuple(
                sorted(
                    self.player_ids
                )
            ),
        )

        self.assertEqual(
            cache.calls[0][1],
            tuple(
                sorted(
                    self.player_ids
                )
            ),
        )

    def test_missing_performances_are_rejected(self):
        cache = FakeProfileCacheService()

        service = (
            CurrentMatchEnrichmentProfileRefreshService(
                profile_cache_service=cache,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly two",
        ):
            service.refresh(
                self.db,
                internal_match_id=999999,
            )

        self.assertEqual(
            cache.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
