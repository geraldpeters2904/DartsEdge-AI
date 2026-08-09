
import unittest

from app.services.prediction_adapter_self_test_service import (
    _fair_odds,
)


class PredictionAdapterDirectSelfTestTests(
    unittest.TestCase
):
    def test_fair_odds_from_probability(self):
        self.assertEqual(
            _fair_odds(0.5),
            2.0,
        )

    def test_invalid_probability_returns_none(self):
        self.assertIsNone(
            _fair_odds(0.0)
        )
        self.assertIsNone(
            _fair_odds(1.0)
        )


if __name__ == "__main__":
    unittest.main()
