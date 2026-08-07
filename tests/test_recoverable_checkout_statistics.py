import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _build_stats,
    _parse_checkout_statistics,
)


class RecoverableCheckoutStatisticsTests(unittest.TestCase):
    def test_impossible_fraction_becomes_missing(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Barry Copeland",
                fraction="4/0",
                percentage="0%",
            ),
            (None, None, None),
        )

    def test_valid_checkout_statistics_are_preserved(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/5",
                percentage="40%",
            ),
            (2, 5, 40.0),
        )

    def test_other_statistics_remain_available(self):
        rows = {
            "average": ("91.25", "88.50"),
            "100+": ("12", "10"),
            "140+": ("6", "5"),
            "180s": ("2", "1"),
            "checkouts": ("4/0", "2/5"),
            "checkout %": ("0%", "40%"),
            "high checkout": ("120", "80"),
            "ton+ checkouts": ("1", "0"),
        }

        stats = _build_stats("Barry Copeland", 0, rows)

        self.assertEqual(stats.three_dart_average, 91.25)
        self.assertEqual(stats.scores_180, 2)
        self.assertEqual(stats.highest_checkout, 120)
        self.assertIsNone(stats.checkout_attempts)
        self.assertIsNone(stats.checkouts_completed)
        self.assertIsNone(stats.checkout_percentage)


if __name__ == "__main__":
    unittest.main()
