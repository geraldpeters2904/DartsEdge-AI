import unittest

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class TransparentPredictionEngineV33Tests(
    unittest.TestCase
):
    def setUp(self):
        self.engine = (
            TransparentPredictionEngineV33()
        )

    def weight(self, name):
        return next(
            feature.weight
            for feature in self.engine.features
            if feature.name == name
        )

    def test_model_version(self):
        self.assertEqual(
            self.engine.MODEL_VERSION,
            "transparent-v3.3",
        )

    def test_recent_form_is_zero(self):
        self.assertEqual(
            self.weight("recent_form"),
            0.0,
        )

    def test_overall_strength_is_zero(self):
        self.assertEqual(
            self.weight(
                "overall_strength"
            ),
            0.0,
        )

    def test_consistency_remains_enabled(self):
        self.assertEqual(
            self.weight(
                "scoring_consistency"
            ),
            0.05,
        )

    def test_scoring_power_is_unchanged(self):
        self.assertEqual(
            self.weight("scoring_power"),
            0.15,
        )


if __name__ == "__main__":
    unittest.main()
