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
        self.assertEqual(
            snapshot.player_a.latest_match_date,
            "2026-08-04",
        )
        self.assertEqual(
            snapshot.player_b.latest_match_date,
            "2026-08-04",
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
        self.assertIsNone(
            snapshot.player_a.latest_match_date,
        )
        self.assertIsNone(
            snapshot.player_b.latest_match_date,
        )


    def test_observed_at_cutoff_never_includes_future_match_date(self):
        from datetime import datetime

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db import Base
        from app.models.match import Match
        from app.models.player import Player
        from app.models.player_match_performance import (
            PlayerMatchPerformance,
        )

        engine_sql = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine_sql)
        Session = sessionmaker(bind=engine_sql)
        db = Session()

        try:
            player = Player(
                id=1,
                name="Player A",
                elo=1500.0,
            )
            opponent = Player(
                id=2,
                name="Player B",
                elo=1500.0,
            )

            prior_match = Match(
                id=10,
                date=date(2026, 8, 4),
                player_a="Player A",
                player_b="Player B",
                status="completed",
            )
            target_match = Match(
                id=20,
                date=date(2026, 8, 5),
                player_a="Player A",
                player_b="Player B",
                status="completed",
            )
            future_match = Match(
                id=30,
                date=date(2026, 8, 6),
                player_a="Player A",
                player_b="Player B",
                status="completed",
            )

            db.add_all([
                player,
                opponent,
                prior_match,
                target_match,
                future_match,
            ])
            db.flush()

            db.add_all([
                PlayerMatchPerformance(
                    match_id=10,
                    player_id=1,
                    opponent_id=2,
                    source_provider="test",
                    observed_at=datetime(2026, 8, 4, 12, 0),
                ),
                PlayerMatchPerformance(
                    match_id=20,
                    player_id=1,
                    opponent_id=2,
                    source_provider="test",
                    observed_at=datetime(2026, 8, 10, 12, 0),
                ),
                PlayerMatchPerformance(
                    match_id=30,
                    player_id=1,
                    opponent_id=2,
                    source_provider="test",
                    observed_at=datetime(2026, 8, 6, 12, 0),
                ),
            ])
            db.commit()

            rows = PredictionSnapshotEngine()._load_history_before_match(
                db,
                player_id=1,
                target_match=target_match,
                competition_code=None,
            )

            self.assertEqual(
                [match.id for _performance, match in rows],
                [10],
            )
        finally:
            db.close()
            engine_sql.dispose()

if __name__ == "__main__":
    unittest.main()
