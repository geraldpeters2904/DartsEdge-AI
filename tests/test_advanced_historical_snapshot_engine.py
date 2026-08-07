import unittest
from datetime import date
from types import SimpleNamespace

from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)


def performance(**changes):
    values = dict(
        won_match=None,
        threw_first=None,
        legs_won=None,
        legs_lost=None,
        three_dart_average=None,
        first_nine_average=None,
        scores_100_plus=None,
        scores_140_plus=None,
        scores_180=None,
        checkout_attempts=None,
        checkouts_completed=None,
        checkout_percentage=None,
        highest_checkout=None,
        observed_at=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


class PlayerQuery:
    def __init__(self, players):
        self.players = players
        self.player_id = None

    def filter(self, expression):
        self.player_id = getattr(
            getattr(expression, "right", None),
            "value",
            None,
        )
        return self

    def first(self):
        return self.players.get(self.player_id)


class FakeDb:
    def __init__(self, players):
        self.players = players

    def query(self, *models):
        return PlayerQuery(self.players)


class AdvancedHistoricalSnapshotEngineTests(
    unittest.TestCase
):
    def test_builds_advanced_input_from_prior_rows(self):
        player_a = SimpleNamespace(
            id=1,
            name="Player A",
        )
        player_b = SimpleNamespace(
            id=2,
            name="Player B",
        )

        rows_a = [
            (
                performance(
                    won_match=True,
                    legs_won=4,
                    legs_lost=2,
                    three_dart_average=94.0,
                    scores_140_plus=5,
                    scores_180=2,
                    checkout_attempts=8,
                    checkouts_completed=4,
                    highest_checkout=120,
                ),
                SimpleNamespace(
                    id=90,
                    date=date(2026, 8, 4),
                ),
            )
        ]

        rows_b = [
            (
                performance(
                    won_match=False,
                    legs_won=1,
                    legs_lost=4,
                    three_dart_average=84.0,
                    scores_140_plus=2,
                    scores_180=0,
                    checkout_attempts=5,
                    checkouts_completed=1,
                    highest_checkout=60,
                ),
                SimpleNamespace(
                    id=89,
                    date=date(2026, 8, 4),
                ),
            )
        ]

        engine = AdvancedHistoricalSnapshotEngine()

        snapshot = engine.build_snapshot_from_history(
            FakeDb({
                1: player_a,
                2: player_b,
            }),
            match=SimpleNamespace(
                id=100,
            ),
            player_a=player_a,
            player_b=player_b,
            history_a=rows_a,
            history_b=rows_b,
        )

        self.assertEqual(
            snapshot.match_id,
            100,
        )
        self.assertEqual(
            snapshot.player_a.player_name,
            "Player A",
        )
        self.assertEqual(
            snapshot.player_a.advanced_features
            .matches_available,
            1,
        )
        self.assertGreater(
            snapshot.player_a.overall_rating,
            snapshot.player_b.overall_rating,
        )

    def test_empty_history_returns_baseline(self):
        player_a = SimpleNamespace(
            id=1,
            name="A",
        )
        player_b = SimpleNamespace(
            id=2,
            name="B",
        )

        snapshot = (
            AdvancedHistoricalSnapshotEngine()
            .build_snapshot_from_history(
                FakeDb({
                    1: player_a,
                    2: player_b,
                }),
                match=SimpleNamespace(id=200),
                player_a=player_a,
                player_b=player_b,
                history_a=[],
                history_b=[],
            )
        )

        self.assertEqual(
            snapshot.player_a.overall_rating,
            1500.0,
        )
        self.assertEqual(
            snapshot.player_b.overall_rating,
            1500.0,
        )


if __name__ == "__main__":
    unittest.main()
