import unittest
from datetime import date
from types import SimpleNamespace

from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)


def performance(
    *,
    won,
    average,
    legs_won,
    legs_lost,
    scores_180,
    attempts,
    completed,
):
    return SimpleNamespace(
        won_match=won,
        legs_won=legs_won,
        legs_lost=legs_lost,
        three_dart_average=average,
        first_nine_average=None,
        scores_100_plus=0,
        scores_140_plus=2,
        scores_180=scores_180,
        checkout_attempts=attempts,
        checkouts_completed=completed,
        checkout_percentage=(
            completed / attempts * 100
            if attempts
            else None
        ),
        highest_checkout=80,
    )


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


class PredictionSnapshotEngineTests(unittest.TestCase):
    def test_builds_snapshot_from_pre_match_history(self):
        engine = PredictionSnapshotEngine()

        player_a = SimpleNamespace(
            id=1,
            name="Player A",
        )
        player_b = SimpleNamespace(
            id=2,
            name="Player B",
        )
        match = SimpleNamespace(
            id=100,
            date=date(2026, 8, 5),
            tournament="MODUS",
            stage="Group A",
        )

        history_a = [
            (
                performance(
                    won=True,
                    average=94.0,
                    legs_won=4,
                    legs_lost=2,
                    scores_180=2,
                    attempts=8,
                    completed=4,
                ),
                SimpleNamespace(
                    id=90,
                    date=date(2026, 8, 4),
                ),
            ),
            (
                performance(
                    won=True,
                    average=92.0,
                    legs_won=4,
                    legs_lost=3,
                    scores_180=1,
                    attempts=6,
                    completed=2,
                ),
                SimpleNamespace(
                    id=89,
                    date=date(2026, 8, 3),
                ),
            ),
        ]

        history_b = [
            (
                performance(
                    won=False,
                    average=84.0,
                    legs_won=1,
                    legs_lost=4,
                    scores_180=0,
                    attempts=4,
                    completed=1,
                ),
                SimpleNamespace(
                    id=88,
                    date=date(2026, 8, 4),
                ),
            )
        ]

        snapshot = engine.build_snapshot_from_history(
            FakeDb({
                1: player_a,
                2: player_b,
            }),
            match=match,
            player_a=player_a,
            player_b=player_b,
            history_a=history_a,
            history_b=history_b,
        )

        self.assertEqual(snapshot.match_id, 100)
        self.assertEqual(
            snapshot.player_a.matches_available,
            2,
        )
        self.assertEqual(
            snapshot.player_b.matches_available,
            1,
        )
        self.assertEqual(
            snapshot.player_a.last_10_wins,
            2,
        )
        self.assertGreater(
            snapshot.overall_edge,
            0,
        )
        self.assertGreater(
            snapshot.scoring_edge,
            0,
        )

    def test_empty_history_returns_baseline_ratings(self):
        engine = PredictionSnapshotEngine()

        player_a = SimpleNamespace(
            id=1,
            name="Debut A",
        )
        player_b = SimpleNamespace(
            id=2,
            name="Debut B",
        )

        snapshot = engine.build_snapshot_from_history(
            FakeDb({
                1: player_a,
                2: player_b,
            }),
            match=SimpleNamespace(
                id=200,
                date=date(2026, 8, 5),
                tournament="MODUS",
                stage="Group A",
            ),
            player_a=player_a,
            player_b=player_b,
            history_a=[],
            history_b=[],
        )

        self.assertEqual(
            snapshot.player_a.overall_rating,
            1500.0,
        )
        self.assertEqual(
            snapshot.player_b.overall_rating,
            1500.0,
        )
        self.assertEqual(snapshot.overall_edge, 0.0)
        self.assertEqual(
            snapshot.player_a.confidence_score,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
