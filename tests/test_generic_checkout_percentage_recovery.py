import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _parse_checkout_statistics,
)


class GenericCheckoutPercentageRecoveryTests(unittest.TestCase):
    def test_known_bradly_roes_mismatch_is_recovered(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Bradly Roes",
                fraction="2/5",
                percentage="33%",
            ),
            (2, 5, 40.0),
        )

    def test_known_richard_rowlands_mismatch_is_recovered(self):
        completed, attempts, percentage = (
            _parse_checkout_statistics(
                player_name="Richard Rowlands",
                fraction="4/9",
                percentage="36%",
            )
        )

        self.assertEqual(completed, 4)
        self.assertEqual(attempts, 9)
        self.assertAlmostEqual(
            percentage,
            44.444,
            places=3,
        )

    def test_unknown_valid_fraction_mismatch_is_recovered(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Any Player",
                fraction="3/8",
                percentage="25%",
            ),
            (3, 8, 37.5),
        )

    def test_matching_percentage_is_unchanged(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Any Player",
                fraction="2/5",
                percentage="40%",
            ),
            (2, 5, 40.0),
        )

    def test_completed_cannot_exceed_attempts(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Any Player",
                fraction="6/5",
                percentage="100%",
            ),
            (None, None, None),
        )

    def test_malformed_fraction_still_fails(self):
        with self.assertRaisesRegex(
            ValueError,
            "completed/attempted",
        ):
            _parse_checkout_statistics(
                player_name="Any Player",
                fraction="not-a-fraction",
                percentage="40%",
            )


if __name__ == "__main__":
    unittest.main()
