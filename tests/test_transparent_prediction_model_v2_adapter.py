import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_model_v2_adapter import (
    TransparentPredictionModelV2Adapter,
)


class FakeEngine:
    def predict(self, snapshot):
        return (
            "predicted",
            snapshot,
        )


class TransparentPredictionModelV2AdapterTests(
    unittest.TestCase
):
    def test_delegates_prediction(self):
        adapter = (
            TransparentPredictionModelV2Adapter(
                engine=FakeEngine()
            )
        )

        snapshot = SimpleNamespace(
            match_id=1,
        )

        self.assertEqual(
            adapter.predict(snapshot),
            ("predicted", snapshot),
        )
        self.assertEqual(
            adapter.MODEL_VERSION,
            "transparent-v2",
        )


if __name__ == "__main__":
    unittest.main()
