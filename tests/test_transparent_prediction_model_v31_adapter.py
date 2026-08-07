import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_model_v31_adapter import (
    TransparentPredictionModelV31Adapter,
)


class FakeEngine:
    def predict(self, snapshot):
        return ("v3.1", snapshot)


class TransparentPredictionModelV31AdapterTests(
    unittest.TestCase
):
    def test_delegates_to_engine(self):
        adapter = (
            TransparentPredictionModelV31Adapter(
                engine=FakeEngine()
            )
        )
        snapshot = SimpleNamespace(match_id=1)

        self.assertEqual(
            adapter.predict(snapshot),
            ("v3.1", snapshot),
        )

    def test_version(self):
        self.assertEqual(
            TransparentPredictionModelV31Adapter
            .MODEL_VERSION,
            "transparent-v3.1",
        )


if __name__ == "__main__":
    unittest.main()
