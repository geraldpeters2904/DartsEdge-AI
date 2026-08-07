import unittest
from pathlib import Path

from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
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

    def test_valid_checkout_values_are_preserved(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/5",
                percentage="40%",
            ),
            (2, 5, 40.0),
        )

    def test_real_corrupt_match_still_parses_when_available(self):
        path = Path(
            "/Users/geraldpeters/Documents/DartsEdge/Imports/"
            "Series_12/Week_09/Group_C/match_15151.html"
        )

        if not path.is_file():
            self.skipTest(
                "Historical match 15151 is not available."
            )

        match = ModusRealMatchPageParser().parse(
            path.read_text(encoding="utf-8"),
            match_id=15151,
        )

        self.assertEqual(match.match_id, 15151)

        checkout_sets = (
            (
                match.player_a_stats.checkout_attempts,
                match.player_a_stats.checkouts_completed,
                match.player_a_stats.checkout_percentage,
            ),
            (
                match.player_b_stats.checkout_attempts,
                match.player_b_stats.checkouts_completed,
                match.player_b_stats.checkout_percentage,
            ),
        )

        self.assertIn(
            (None, None, None),
            checkout_sets,
        )


if __name__ == "__main__":
    unittest.main()
