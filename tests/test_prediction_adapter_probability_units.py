import unittest

from app.services.prediction_adapter_self_test_service import (
    _fair_odds,
    _normalise_probability,
)


class PredictionAdapterProbabilityUnitsTests(unittest.TestCase):
    def test_percentage_probability_is_normalised(self):
        self.assertAlmostEqual(
            _normalise_probability(54.426),
            0.54426,
            places=6,
        )

    def test_decimal_probability_is_preserved(self):
        self.assertEqual(
            _normalise_probability(0.54426),
            0.54426,
        )

    def test_percentage_probability_produces_fair_odds(self):
        self.assertAlmostEqual(
            _fair_odds(54.426),
            1.8374,
            places=4,
        )

    def test_percentage_confidence_range_is_supported(self):
        self.assertAlmostEqual(
            _normalise_probability(37.656),
            0.37656,
            places=6,
        )


    def test_exact_one_remains_invalid_boundary(self):
        self.assertIsNone(
            _normalise_probability(1.0)
        )
        self.assertIsNone(
            _fair_odds(1.0)
        )


if __name__ == "__main__":
    unittest.main()
