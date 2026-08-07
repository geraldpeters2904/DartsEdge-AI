import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _parse_checkout_statistics,
)


class RecoverableCheckoutPercentageMismatchTests(
    unittest.TestCase
):
    def test_bradly_roes_uses_fraction_percentage(self):
        completed, attempts, percentage = (
            _parse_checkout_statistics(
                player_name="Bradly Roes",
                fraction="2/5",
                percentage="33%",
            )
        )

        self.assertEqual(
            (completed, attempts, percentage),
            (2, 5, 40.0),
        )

    def test_richard_rowlands_uses_fraction_percentage(self):
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

    def test_unknown_valid_mismatch_is_recovered(self):
        completed, attempts, percentage = (
            _parse_checkout_statistics(
                player_name="Unknown Player",
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


if __name__ == "__main__":
    unittest.main()
