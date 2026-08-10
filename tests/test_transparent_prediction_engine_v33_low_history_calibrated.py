import unittest
from dataclasses import dataclass
from types import SimpleNamespace

from app.services.transparent_prediction_engine_v33_low_history_calibrated import (
    TransparentPredictionEngineV33LowHistoryCalibrated,
)


@dataclass(frozen=True)
class FakePrediction:
    player_a_probability: float
    player_b_probability: float
    predicted_winner: str
    model_version: str
    model_score: float
    contributions: tuple
    explanation: tuple


class FakeBaseEngine:
    def __init__(
        self,
        *,
        probability_a,
        probability_b,
        winner,
    ):
        self.probability_a = probability_a
        self.probability_b = probability_b
        self.winner = winner

    def predict(self, snapshot):
        return FakePrediction(
            player_a_probability=self.probability_a,
            player_b_probability=self.probability_b,
            predicted_winner=self.winner,
            model_version="transparent-v3.3",
            model_score=0.123,
            contributions=("feature-a",),
            explanation=("example",),
        )


def snapshot(
    history_a,
    history_b,
):
    return SimpleNamespace(
        player_a=SimpleNamespace(
            advanced_features=SimpleNamespace(
                matches_available=history_a
            )
        ),
        player_b=SimpleNamespace(
            advanced_features=SimpleNamespace(
                matches_available=history_b
            )
        ),
    )


class TransparentPredictionEngineV33LowHistoryCalibratedTests(
    unittest.TestCase
):
    def test_twenty_percent_shrink_moves_67_to_63_6(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.20,
                base_engine=FakeBaseEngine(
                    probability_a=67.0,
                    probability_b=33.0,
                    winner="Player A",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                5,
                20,
            )
        )

        self.assertEqual(
            result.player_a_probability,
            63.6,
        )

        self.assertEqual(
            result.player_b_probability,
            36.4,
        )

    def test_predicted_winner_is_preserved(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.40,
                base_engine=FakeBaseEngine(
                    probability_a=34.0,
                    probability_b=66.0,
                    winner="Player B",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                4,
                18,
            )
        )

        self.assertEqual(
            result.predicted_winner,
            "Player B",
        )

        self.assertEqual(
            result.player_b_probability,
            59.6,
        )

        self.assertEqual(
            result.player_a_probability,
            40.4,
        )

    def test_non_target_probability_is_unchanged(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.30,
                base_engine=FakeBaseEngine(
                    probability_a=72.0,
                    probability_b=28.0,
                    winner="Player A",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                3,
                20,
            )
        )

        self.assertEqual(
            result.player_a_probability,
            72.0,
        )

        self.assertEqual(
            result.player_b_probability,
            28.0,
        )

    def test_established_history_is_unchanged(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.30,
                base_engine=FakeBaseEngine(
                    probability_a=67.0,
                    probability_b=33.0,
                    winner="Player A",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                10,
                25,
            )
        )

        self.assertEqual(
            result.player_a_probability,
            67.0,
        )

        self.assertEqual(
            result.player_b_probability,
            33.0,
        )

    def test_zero_shrink_is_numerically_unchanged(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.0,
                base_engine=FakeBaseEngine(
                    probability_a=67.0,
                    probability_b=33.0,
                    winner="Player A",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                2,
                30,
            )
        )

        self.assertEqual(
            result.player_a_probability,
            67.0,
        )

        self.assertEqual(
            result.player_b_probability,
            33.0,
        )

    def test_model_version_identifies_shrink_strength(self):
        engine = (
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.20,
                base_engine=FakeBaseEngine(
                    probability_a=67.0,
                    probability_b=33.0,
                    winner="Player A",
                ),
            )
        )

        result = engine.predict(
            snapshot(
                5,
                20,
            )
        )

        self.assertEqual(
            result.model_version,
            "transparent-v3.3-low-history-calibrated-shrink-20",
        )

    def test_rejects_invalid_shrink_fraction(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 1",
        ):
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=1.2,
            )

    def test_rejects_invalid_probability_band(self):
        with self.assertRaisesRegex(
            ValueError,
            "must exceed",
        ):
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.20,
                probability_lower=70.0,
                probability_upper=65.0,
            )

    def test_rejects_invalid_history_limit(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            TransparentPredictionEngineV33LowHistoryCalibrated(
                shrink_fraction=0.20,
                minimum_history_upper=0,
            )


if __name__ == "__main__":
    unittest.main()
