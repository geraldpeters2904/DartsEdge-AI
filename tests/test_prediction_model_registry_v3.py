import unittest

from app.services.prediction_model_registry import (
    PredictionModelRegistry,
)


class PredictionModelRegistryV3Tests(unittest.TestCase):
    def test_default_registry_contains_v3_challenger(self):
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
            registry.versions()["transparent-v3"],
            "transparent-v3",
        )


if __name__ == "__main__":
    unittest.main()
