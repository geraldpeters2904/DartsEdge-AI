import unittest

from app.services.fixture_edge_service import (
    classify_edge,
    decimal_odds_to_implied_probability,
    expected_value_percent,
    probability_to_fair_odds,
)


class FixtureEdgeMathTests(unittest.TestCase):
    def test_fair_odds(self):
        self.assertEqual(
            probability_to_fair_odds(
                0.5
            ),
            2.0,
        )

    def test_implied_probability(self):
        self.assertEqual(
            decimal_odds_to_implied_probability(
                2.0
            ),
            0.5,
        )

    def test_expected_value(self):
        self.assertEqual(
            expected_value_percent(
                model_probability=0.55,
                decimal_odds=2.0,
            ),
            10.0,
        )

    def test_classification(self):
        self.assertEqual(
            classify_edge(
                6.0
            ),
            "STRONG VALUE",
        )

        self.assertEqual(
            classify_edge(
                3.0
            ),
            "VALUE",
        )

        self.assertEqual(
            classify_edge(
                1.0
            ),
            "WATCH",
        )

        self.assertEqual(
            classify_edge(
                -1.0
            ),
            "NO BET",
        )


if __name__ == "__main__":
    unittest.main()
