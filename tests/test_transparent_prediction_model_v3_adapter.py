import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_model_v3_adapter import (
    TransparentPredictionModelV3Adapter,
)


class FakeEngine:
    def predict(self, snapshot):
        return ("v3", snapshot)


class TransparentPredictionModelV3AdapterTests(
    unittest.TestCase
):
    def test_delegates_prediction(self):
        adapter = TransparentPredictionModelV3Adapter(
            engine=FakeEngine()
        )
        snapshot = SimpleNamespace(match_id=1)

        self.assertEqual(
            adapter.predict(snapshot),
            ("v3", snapshot),
        )
        self.assertEqual(
            adapter.MODEL_VERSION,
            "transparent-v3",
        )


if __name__ == "__main__":
    unittest.main()
