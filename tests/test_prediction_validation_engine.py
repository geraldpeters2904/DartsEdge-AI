import unittest
from datetime import date
from types import SimpleNamespace

from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
)


class FakeMatchQuery:
    def __init__(self, matches):
        self.matches = matches

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.matches


class FakeDb:
    def __init__(self, matches):
        self.matches = matches

    def query(self, *models):
        return FakeMatchQuery(self.matches)


class FakeSnapshotEngine:
    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code=None,
    ):
        return SimpleNamespace(
            match_id=match_id,
        )


class FakePredictionEngine:
    MODEL_VERSION = "test-v1"

    def __init__(self, predictions):
        self.predictions = predictions

    def predict(self, snapshot):
        return self.predictions[
            snapshot.match_id
        ]


def prediction(
    *,
    match_id,
    player_a,
    player_b,
    probability_a,
    winner,
    confidence,
):
    return SimpleNamespace(
        match_id=match_id,
        player_a_name=player_a,
        player_b_name=player_b,
        player_a_probability=probability_a,
        player_b_probability=(
            100.0 - probability_a
        ),
        predicted_winner=winner,
        confidence=confidence,
        model_version="test-v1",
    )


class PredictionValidationEngineTests(
    unittest.TestCase
):
    def setUp(self):
        self.matches = [
            SimpleNamespace(
                id=1,
                date=date(2026, 8, 1),
                tournament="MODUS",
                stage="Group A",
                status="completed",
                player_a="Player A",
                player_b="Player B",
                winner="Player A",
            ),
            SimpleNamespace(
                id=2,
                date=date(2026, 8, 2),
                tournament="MODUS",
                stage="Final",
                status="completed",
                player_a="Player C",
                player_b="Player D",
                winner="Player D",
            ),
        ]

        predictions = {
            1: prediction(
                match_id=1,
                player_a="Player A",
                player_b="Player B",
                probability_a=70.0,
                winner="Player A",
                confidence=80.0,
            ),
            2: prediction(
                match_id=2,
                player_a="Player C",
                player_b="Player D",
                probability_a=60.0,
                winner="Player C",
                confidence=70.0,
            ),
        }

        self.engine = PredictionValidationEngine(
            snapshot_engine=(
                FakeSnapshotEngine()
            ),
            prediction_engine=(
                FakePredictionEngine(
                    predictions
                )
            ),
        )

    def test_builds_validation_report(self):
        report = self.engine.validate_matches(
            FakeDb(self.matches)
        )

        self.assertEqual(
            report.matches_considered,
            2,
        )
        self.assertEqual(
            report.matches_evaluated,
            2,
        )
        self.assertEqual(
            report.correct_predictions,
            1,
        )
        self.assertEqual(
            report.accuracy,
            50.0,
        )
        self.assertEqual(
            report.model_version,
            "test-v1",
        )
        self.assertEqual(
            len(report.records),
            2,
        )

    def test_calibration_uses_favourite_result(self):
        report = self.engine.validate_matches(
            FakeDb(self.matches)
        )

        bucket_60 = next(
            item
            for item in report.calibration
            if item.lower_bound == 60
        )
        bucket_70 = next(
            item
            for item in report.calibration
            if item.lower_bound == 70
        )

        self.assertEqual(
            bucket_60.predictions,
            1,
        )
        self.assertEqual(
            bucket_60.observed_win_rate,
            0.0,
        )
        self.assertEqual(
            bucket_70.predictions,
            1,
        )
        self.assertEqual(
            bucket_70.observed_win_rate,
            100.0,
        )

    def test_skips_invalid_result(self):
        invalid = SimpleNamespace(
            id=3,
            date=date(2026, 8, 3),
            tournament="MODUS",
            stage="Group A",
            status="completed",
            player_a="Player E",
            player_b="Player F",
            winner=None,
        )

        report = self.engine.validate_matches(
            FakeDb(
                self.matches + [invalid]
            )
        )

        self.assertEqual(
            report.matches_considered,
            3,
        )
        self.assertEqual(
            report.matches_evaluated,
            2,
        )
        self.assertEqual(
            report.matches_skipped,
            1,
        )

    def test_can_omit_individual_records(self):
        report = self.engine.validate_matches(
            FakeDb(self.matches),
            include_records=False,
        )

        self.assertEqual(report.records, ())
        self.assertEqual(
            report.matches_evaluated,
            2,
        )

    def test_empty_selection_returns_empty_report(self):
        report = self.engine.validate_matches(
            FakeDb(self.matches),
            match_ids=(),
        )

        self.assertEqual(
            report.matches_considered,
            0,
        )
        self.assertIsNone(report.accuracy)


if __name__ == "__main__":
    unittest.main()
