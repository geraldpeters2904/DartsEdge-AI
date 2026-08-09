
import unittest

from app.services.fixture_prediction_adapter_service import (
    _fair_odds,
    _probability,
)


class FixturePredictionAdapterTests(
    unittest.TestCase
):
    def test_probability_accepts_decimal(
        self,
    ):
        self.assertEqual(
            _probability(
                0.62
            ),
            0.62,
        )

    def test_probability_accepts_percent(
        self,
    ):
        self.assertEqual(
            _probability(
                62
            ),
            0.62,
        )

    def test_fair_odds(
        self,
    ):
        self.assertEqual(
            _fair_odds(
                0.5
            ),
            2.0,
        )


if __name__ == "__main__":
    unittest.main()
