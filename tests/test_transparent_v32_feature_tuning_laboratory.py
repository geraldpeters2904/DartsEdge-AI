import unittest

from app.services.transparent_prediction_engine_v32 import (
    TransparentPredictionEngineV32,
)
from app.services.transparent_v32_feature_tuning_laboratory import (
    TransparentV32FeatureTuningLaboratory,
)


class TransparentV32FeatureTuningLaboratoryTests(
    unittest.TestCase
):
    def test_weight_update_preserves_v32(self):
        engine = TransparentPredictionEngineV32()

        candidate = (
            TransparentV32FeatureTuningLaboratory
            ._with_weight(
                engine,
                "scoring_consistency",
                0.03,
            )
        )

        self.assertIsInstance(
            candidate,
            TransparentPredictionEngineV32,
        )

        weight = next(
            feature.weight
            for feature in candidate.features
            if feature.name
            == "scoring_consistency"
        )

        self.assertEqual(weight, 0.03)

    def test_difference_is_left_minus_right(self):
        self.assertEqual(
            TransparentV32FeatureTuningLaboratory
            ._difference(
                0.28,
                0.26,
            ),
            0.02,
        )

    def test_confidence(self):
        self.assertEqual(
            TransparentV32FeatureTuningLaboratory
            ._confidence(1.0),
            "high",
        )


if __name__ == "__main__":
    unittest.main()
