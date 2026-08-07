import unittest

from app.services.prediction_model_registry import (
    PredictionModelRegistry,
)


class FakeModel:
    MODEL_VERSION = "fake-v1"

    def predict(self, snapshot):
        return snapshot


class PredictionModelRegistryTests(unittest.TestCase):
    def test_default_registry_contains_transparent(self):
        registry = PredictionModelRegistry()

        self.assertEqual(
            registry.names(),
            [
                "transparent",
                "transparent-v2",
                "transparent-v3",
                "transparent-v3.1",
                "transparent-v3.2",
                "transparent-v3.3",
            ],
        )
        self.assertEqual(
            registry.default_name,
            "transparent",
        )
        self.assertEqual(
            registry.versions()["transparent"],
            "transparent-v1",
        )
        self.assertEqual(
            registry.versions()["transparent-v2"],
            "transparent-v2",
        )

    def test_register_and_select_model(self):
        registry = PredictionModelRegistry(
            models=[
                ("fake", FakeModel()),
            ],
            default_model="fake",
        )

        self.assertIsInstance(
            registry.get(),
            FakeModel,
        )
        self.assertEqual(
            registry.get_registered().version,
            "fake-v1",
        )

    def test_unknown_model_raises(self):
        registry = PredictionModelRegistry()

        with self.assertRaisesRegex(
            ValueError,
            "Unknown prediction model",
        ):
            registry.get("missing")


if __name__ == "__main__":
    unittest.main()
