
import unittest

from app.services.prediction_readiness_dashboard_service import (
    _best_verdict,
)


class PredictionReadinessDashboardTests(unittest.TestCase):
    def test_best_verdict_uses_highest_value_rank(self):
        self.assertEqual(
            _best_verdict(
                [
                    "NO BET",
                    "WATCH",
                    "VALUE",
                    "STRONG VALUE",
                ]
            ),
            "STRONG VALUE",
        )

    def test_empty_verdicts_return_no_market(self):
        self.assertEqual(
            _best_verdict([]),
            "NO MARKET",
        )


if __name__ == "__main__":
    unittest.main()
