import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _parse_checkout_statistics,
)


class RecoverableCheckoutStatisticsNarrowTests(unittest.TestCase):
    def test_impossible_fraction_becomes_missing(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Barry Copeland",
                fraction="4/0",
                percentage="0%",
            ),
            (None, None, None),
        )

    def test_percentage_mismatch_is_recovered(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/4",
                percentage="40%",
            ),
            (2, 4, 50.0),
        )

    def test_valid_statistics_are_preserved(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/4",
                percentage="50%",
            ),
            (2, 4, 50.0),
        )


if __name__ == "__main__":
    unittest.main()
