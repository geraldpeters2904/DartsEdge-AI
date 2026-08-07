import unittest

from app.services.transparent_v3_feature_contribution import (
    TransparentV3FeatureContributionLaboratory,
)


class TransparentV3FeatureContributionTests(
    unittest.TestCase
):
    def test_positive_deltas_mean_feature_is_helpful(self):
        score = (
            TransparentV3FeatureContributionLaboratory
            ._importance_score(
                accuracy_drop=2.0,
                brier_increase=0.01,
                log_loss_increase=0.02,
            )
        )

        self.assertGreater(score, 0)

    def test_negative_deltas_mean_feature_is_harmful(self):
        score = (
            TransparentV3FeatureContributionLaboratory
            ._importance_score(
                accuracy_drop=-1.0,
                brier_increase=-0.01,
                log_loss_increase=-0.02,
            )
        )

        self.assertLess(score, 0)

    def test_ablation_preserves_total_weight(self):
        from app.services.transparent_prediction_engine_v3 import (
            TransparentPredictionEngineV3,
        )

        engine = TransparentPredictionEngineV3()

        candidate = (
            TransparentV3FeatureContributionLaboratory
            ._without_feature_normalised(
                engine,
                "checkout_trend",
            )
        )

        original_total = sum(
            feature.weight
            for feature in engine.features
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
            "checkout_trend",
            candidate.feature_names(),
        )

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            TransparentV3FeatureContributionLaboratory
            ._difference(
                None,
                1.0,
            )
        )

    def test_difference_is_left_minus_right(self):
        self.assertEqual(
            TransparentV3FeatureContributionLaboratory
            ._difference(
                60.0,
                58.5,
            ),
            1.5,
        )


if __name__ == "__main__":
    unittest.main()
