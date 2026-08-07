import unittest

from app.services.transparent_prediction_engine_v31 import (
    TransparentPredictionEngineV31,
)


class TransparentPredictionEngineV31Tests(
    unittest.TestCase
):
    def test_recent_form_weight_is_zero(self):
        engine = TransparentPredictionEngineV31()

        recent_form = next(
            feature
            for feature in engine.features
            if feature.name == "recent_form"
        )

        self.assertEqual(
            recent_form.weight,
            0.0,
        )

    def test_other_weights_are_unchanged(self):
        engine = TransparentPredictionEngineV31()

        scoring = next(
            feature
            for feature in engine.features
            if feature.name == "scoring_power"
        )

        self.assertEqual(
            scoring.weight,
            0.15,
        )

    def test_model_version_is_v31(self):
        self.assertEqual(
            TransparentPredictionEngineV31
            .MODEL_VERSION,
            "transparent-v3.1",
        )

    def test_recent_form_plugin_remains_available(self):
        engine = TransparentPredictionEngineV31()

        self.assertIn(
            "recent_form",
            engine.feature_names(),
        )


if __name__ == "__main__":
    unittest.main()
