import unittest

from app.providers.adapters.modus_official.real_match_parser import (
    _parse_checkout_statistics,
)


class BradlyRoesCheckoutRecoveryTests(unittest.TestCase):
    def test_known_modus_percentage_error_uses_fraction(self):
        completed, attempts, percentage = (
            _parse_checkout_statistics(
                player_name="Bradly Roes",
                fraction="2/5",
                percentage="33%",
            )
        )

        self.assertEqual(completed, 2)
        self.assertEqual(attempts, 5)
        self.assertEqual(percentage, 40.0)

    def test_other_valid_percentage_mismatch_is_recovered(self):
        self.assertEqual(
            _parse_checkout_statistics(
                player_name="Different Player",
                fraction="2/5",
                percentage="33%",
            ),
            (2, 5, 40.0),
        )


if __name__ == "__main__":
    unittest.main()
