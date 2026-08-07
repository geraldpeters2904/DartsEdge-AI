import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from app.services.prediction_stability_service import (
    analyse_snapshot_stability,
    stability_summary,
)


@dataclass(frozen=True)
class Player:
    player_name: str
    overall_rating: float
    scoring_rating: float
    finishing_rating: float
    maximums_rating: float
    form_rating: float


@dataclass(frozen=True)
class Snapshot:
    match_id: int
    player_a: Player
    player_b: Player


class FakePredictionEngine:
    def predict(self, snapshot):
        edge = (
            snapshot.player_a.scoring_rating
            - snapshot.player_b.scoring_rating
        )

        probability = round(
            50.0 + edge * 0.10,
            3,
        )

        winner = (
            snapshot.player_a.player_name
            if probability >= 50.0
            else snapshot.player_b.player_name
        )

        return SimpleNamespace(
            player_a_probability=(
                probability
            ),
            player_b_probability=(
                100.0 - probability
            ),
            predicted_winner=winner,
            player_a_name=(
                snapshot.player_a
                .player_name
            ),
            player_b_name=(
                snapshot.player_b
                .player_name
            ),
            model_version=(
                "transparent-v3.3"
            ),
        )


class PredictionStabilityServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.snapshot = Snapshot(
            match_id=101,
            player_a=Player(
                player_name="Alpha",
                overall_rating=1500.0,
                scoring_rating=1560.0,
                finishing_rating=1520.0,
                maximums_rating=1530.0,
                form_rating=1540.0,
            ),
            player_b=Player(
                player_name="Bravo",
                overall_rating=1500.0,
                scoring_rating=1500.0,
                finishing_rating=1500.0,
                maximums_rating=1500.0,
                form_rating=1500.0,
            ),
        )

    def test_builds_stability_report(self):
        report = analyse_snapshot_stability(
            self.snapshot,
            prediction_engine=(
                FakePredictionEngine()
            ),
        )

        self.assertEqual(
            report.match_id,
            101,
        )
        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            report.simulation_count,
            10,
        )
        self.assertGreaterEqual(
            report.stability_score,
            0,
        )
        self.assertLessEqual(
            report.stability_score,
            100,
        )

    def test_ranks_scoring_as_most_sensitive(self):
        report = analyse_snapshot_stability(
            self.snapshot,
            prediction_engine=(
                FakePredictionEngine()
            ),
        )

        self.assertEqual(
            report.most_sensitive_feature,
            "scoring_rating",
        )

    def test_original_snapshot_is_unchanged(self):
        analyse_snapshot_stability(
            self.snapshot,
            prediction_engine=(
                FakePredictionEngine()
            ),
        )

        self.assertEqual(
            self.snapshot.player_a
            .scoring_rating,
            1560.0,
        )
        self.assertEqual(
            self.snapshot.player_b
            .scoring_rating,
            1500.0,
        )

    def test_summary_is_json_ready(self):
        payload = stability_summary(
            analyse_snapshot_stability(
                self.snapshot,
                prediction_engine=(
                    FakePredictionEngine()
                ),
            )
        )

        self.assertIsInstance(
            payload["sensitivities"],
            list,
        )
        self.assertIsInstance(
            payload[
                "positive_reasons"
            ],
            list,
        )
        self.assertIn(
            "stability_score",
            payload,
        )


if __name__ == "__main__":
    unittest.main()
