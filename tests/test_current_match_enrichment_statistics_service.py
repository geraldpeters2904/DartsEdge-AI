import unittest
from dataclasses import dataclass
from datetime import datetime

from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsService,
)


@dataclass
class FakePlayerStats:
    player_name: str
    three_dart_average: float
    scores_100_plus: int
    scores_140_plus: int
    scores_180: int
    checkout_attempts: int
    checkouts_completed: int
    checkout_percentage: float
    highest_checkout: int
    ton_plus_checkouts: int


@dataclass
class FakeDetail:
    match_id: int = 19001
    player_a_name: str = "Player A"
    player_b_name: str = "Player B"
    player_a_legs: int = 4
    player_b_legs: int = 2
    player_a_stats: object = None
    player_b_stats: object = None

    def __post_init__(self):
        if self.player_a_stats is None:
            self.player_a_stats = FakePlayerStats(
                player_name="Player A",
                three_dart_average=92.5,
                scores_100_plus=11,
                scores_140_plus=6,
                scores_180=2,
                checkout_attempts=8,
                checkouts_completed=4,
                checkout_percentage=50.0,
                highest_checkout=121,
                ton_plus_checkouts=1,
            )

        if self.player_b_stats is None:
            self.player_b_stats = FakePlayerStats(
                player_name="Player B",
                three_dart_average=88.1,
                scores_100_plus=9,
                scores_140_plus=5,
                scores_180=1,
                checkout_attempts=6,
                checkouts_completed=2,
                checkout_percentage=33.333,
                highest_checkout=96,
                ton_plus_checkouts=0,
            )


@dataclass
class FakeDetailResult:
    internal_match_id: int = 101
    modus_match_id: int = 19001
    detail: object = None
    status: str = "validated"

    def __post_init__(self):
        if self.detail is None:
            self.detail = FakeDetail()


class CurrentMatchEnrichmentStatisticsServiceTests(
    unittest.TestCase
):
    def test_builds_two_canonical_statistics_records(self):
        service = CurrentMatchEnrichmentStatisticsService()

        observed_at = datetime(
            2026,
            8,
            9,
            20,
            30,
        )

        result = service.build(
            FakeDetailResult(),
            retrieved_at=observed_at,
        )

        self.assertEqual(
            result.status,
            "canonicalized",
        )
        self.assertEqual(
            result.match_external_id,
            "modus-match-19001",
        )
        self.assertEqual(
            len(result.statistics),
            2,
        )

        first, second = result.statistics

        self.assertEqual(
            first.player_external_id,
            "modus-player-player-a",
        )
        self.assertEqual(
            second.player_external_id,
            "modus-player-player-b",
        )

        self.assertEqual(
            first.legs_won,
            4,
        )
        self.assertEqual(
            first.legs_lost,
            2,
        )
        self.assertEqual(
            second.legs_won,
            2,
        )
        self.assertEqual(
            second.legs_lost,
            4,
        )

        self.assertEqual(
            first.scores_180,
            2,
        )
        self.assertEqual(
            second.scores_180,
            1,
        )

        self.assertEqual(
            first.source.provider,
            "modus-official",
        )
        self.assertEqual(
            first.source.external_id,
            (
                "modus:statistics:19001:"
                "modus-player-player-a"
            ),
        )
        self.assertEqual(
            first.source.retrieved_at,
            observed_at,
        )

    def test_unvalidated_detail_is_rejected(self):
        service = CurrentMatchEnrichmentStatisticsService()

        result = FakeDetailResult(
            status="error",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only validated",
        ):
            service.build(result)

    def test_mismatched_match_id_is_rejected(self):
        service = CurrentMatchEnrichmentStatisticsService()

        result = FakeDetailResult()
        result.detail.match_id = 99999

        with self.assertRaisesRegex(
            ValueError,
            "match ID does not match",
        ):
            service.build(result)


if __name__ == "__main__":
    unittest.main()
