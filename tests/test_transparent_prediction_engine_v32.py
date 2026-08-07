import unittest

from app.services.transparent_prediction_engine_v32 import (
    TransparentPredictionEngineV32,
)


class TransparentPredictionEngineV32Tests(
    unittest.TestCase
):
    def test_version(self):
        self.assertEqual(
            TransparentPredictionEngineV32
            .MODEL_VERSION,
            "transparent-v3.2",
        )

    def test_consistency_feature_is_present(self):
        engine = TransparentPredictionEngineV32()

        self.assertIn(
            "scoring_consistency",
            engine.feature_names(),
        )

    def test_recent_form_remains_disabled(self):
        engine = TransparentPredictionEngineV32()

        feature = next(
            item
            for item in engine.features
            if item.name == "recent_form"
        )

        self.assertEqual(feature.weight, 0.0)

    def test_consistency_weight(self):
        engine = TransparentPredictionEngineV32()

        feature = next(
            item
            for item in engine.features
            if item.name
            == "scoring_consistency"
        )

        self.assertEqual(feature.weight, 0.05)


if __name__ == "__main__":
    unittest.main()
