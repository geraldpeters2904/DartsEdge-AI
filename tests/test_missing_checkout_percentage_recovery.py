import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _parse_checkout_statistics,
)


class MissingCheckoutPercentageRecoveryTests(
    unittest.TestCase
):
    def test_zero_from_four_with_dash_percentage(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Carl Wilson",
                fraction="0/4",
                percentage="--%",
            ),
            (0, 4, 0.0),
        )

    def test_zero_from_one_with_dash_percentage(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Gemma Hayter",
                fraction="0/1",
                percentage="--%",
            ),
            (0, 1, 0.0),
        )

    def test_nonzero_fraction_with_missing_percentage_is_derived(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/5",
                percentage="--%",
            ),
            (2, 5, 40.0),
        )

    def test_unrecognised_percentage_text_still_fails(self):
        with self.assertRaisesRegex(
            ValueError,
            "number between 0 and 100",
        ):
            _parse_checkout_statistics(
                player_name="Example Player",
                fraction="2/5",
                percentage="unknown",
            )


if __name__ == "__main__":
    unittest.main()
