import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_challenger_service import (
    CurrentMatchEnrichmentV33ChallengerService,
    V33ChallengerConfiguration,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class CurrentMatchEnrichmentV33ChallengerServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33ChallengerService()
        )

    def test_challenger_preserves_v33_engine(self):
        baseline = TransparentPredictionEngineV33()

        challenger = self.service._engine_with_weights(
            baseline,
            {
                "recent_win_rate": 0.04,
                "finishing_strength": 0.08,
            },
        )

        self.assertIsInstance(
            challenger,
            TransparentPredictionEngineV33,
        )

        self.assertEqual(
            challenger.MODEL_VERSION,
            "transparent-v3.3",
        )

    def test_only_requested_weights_change(self):
        baseline = TransparentPredictionEngineV33()

        challenger = self.service._engine_with_weights(
            baseline,
            {
                "recent_win_rate": 0.04,
            },
        )

        baseline_weights = {
            feature.name: feature.weight
            for feature in baseline.features
        }

        challenger_weights = {
            feature.name: feature.weight
            for feature in challenger.features
        }

        self.assertEqual(
            challenger_weights["recent_win_rate"],
            0.04,
        )

        for name, weight in baseline_weights.items():
            if name == "recent_win_rate":
                continue

            self.assertEqual(
                challenger_weights[name],
                weight,
            )

    def test_unknown_feature_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown v3.3 feature",
        ):
            self.service._engine_with_weights(
                TransparentPredictionEngineV33(),
                {
                    "not-a-feature": 0.05,
                },
            )

    def test_negative_weight_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            self.service._engine_with_weights(
                TransparentPredictionEngineV33(),
                {
                    "recent_win_rate": -0.01,
                },
            )

    def test_probability_improvement_with_safe_accuracy_is_accepted(
        self,
    ):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        self.assertTrue(
            self.service._accepted(
                baseline=baseline,
                accuracy=59.0,
                brier_score=0.24,
                log_loss=0.69,
            )
        )

    def test_material_accuracy_loss_is_rejected(self):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        self.assertFalse(
            self.service._accepted(
                baseline=baseline,
                accuracy=57.0,
                brier_score=0.24,
                log_loss=0.69,
            )
        )

    def test_both_probability_metrics_must_improve(self):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        self.assertFalse(
            self.service._accepted(
                baseline=baseline,
                accuracy=60.0,
                brier_score=0.24,
                log_loss=0.71,
            )
        )

    def test_difference_is_left_minus_right(self):
        self.assertEqual(
            self.service._difference(
                0.25,
                0.20,
            ),
            0.05,
        )

        self.assertIsNone(
            self.service._difference(
                None,
                0.20,
            )
        )

    def test_configuration_dataclass_preserves_weights(self):
        configuration = V33ChallengerConfiguration(
            name="challenger-a",
            weights={
                "recent_win_rate": 0.04,
            },
        )

        self.assertEqual(
            configuration.name,
            "challenger-a",
        )

        self.assertEqual(
            configuration.weights[
                "recent_win_rate"
            ],
            0.04,
        )


if __name__ == "__main__":
    unittest.main()
