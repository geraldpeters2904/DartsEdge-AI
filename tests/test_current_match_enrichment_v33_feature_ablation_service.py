import unittest

from app.services.current_match_enrichment_v33_feature_ablation_service import (
    CurrentMatchEnrichmentV33FeatureAblationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class CurrentMatchEnrichmentV33FeatureAblationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33FeatureAblationService()
        )
        self.engine = (
            TransparentPredictionEngineV33()
        )

    def test_ablation_preserves_v33_engine(self):
        candidate = (
            self.service
            ._without_feature_normalised(
                self.engine,
                "scoring_power",
            )
        )

        self.assertIsInstance(
            candidate,
            TransparentPredictionEngineV33,
        )

        self.assertEqual(
            candidate.MODEL_VERSION,
            "transparent-v3.3",
        )

    def test_ablation_preserves_total_weight(self):
        candidate = (
            self.service
            ._without_feature_normalised(
                self.engine,
                "scoring_power",
            )
        )

        original_total = sum(
            feature.weight
            for feature in self.engine.features
        )

        candidate_total = sum(
            feature.weight
            for feature in candidate.features
        )

        self.assertAlmostEqual(
            candidate_total,
            original_total,
            places=9,
        )

        self.assertNotIn(
            "scoring_power",
            candidate.feature_names(),
        )

    def test_zero_weight_feature_cannot_be_ablated(self):
        with self.assertRaisesRegex(
            ValueError,
            "zero-weight",
        ):
            self.service._without_feature_normalised(
                self.engine,
                "overall_strength",
            )

    def test_unknown_feature_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown prediction feature",
        ):
            self.service._without_feature_normalised(
                self.engine,
                "not-a-feature",
            )

    def test_positive_metrics_mean_helpful_feature(self):
        score = self.service._importance_score(
            accuracy_drop=2.0,
            brier_increase=0.01,
            log_loss_increase=0.02,
        )

        self.assertGreater(
            score,
            0.0,
        )

    def test_negative_metrics_mean_harmful_feature(self):
        score = self.service._importance_score(
            accuracy_drop=-2.0,
            brier_increase=-0.01,
            log_loss_increase=-0.02,
        )

        self.assertLess(
            score,
            0.0,
        )

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            self.service._difference(
                None,
                1.0,
            )
        )

    def test_difference_is_left_minus_right(self):
        self.assertEqual(
            self.service._difference(
                0.30,
                0.27,
            ),
            0.03,
        )


if __name__ == "__main__":
    unittest.main()
