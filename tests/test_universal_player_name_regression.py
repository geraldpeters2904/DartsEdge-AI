import unittest

from app.services.player_name_service import (
    normalise_player_name,
    player_alias_key,
)


class UniversalPlayerNameRegressionTests(unittest.TestCase):
    def test_all_apostrophe_variants_match(self):
        variants = (
            "John O'Shea",
            "John O’Shea",
            "John O´Shea",
            "John O`Shea",
            "John OʼShea",
            "John O＇Shea",
        )

        self.assertEqual(
            {
                normalise_player_name(value)
                for value in variants
            },
            {"john o'shea"},
        )

        self.assertEqual(
            {
                player_alias_key(value)
                for value in variants
            },
            {"johnoshea"},
        )

    def test_accented_letter_is_not_treated_as_apostrophe(self):
        self.assertEqual(
            normalise_player_name("John ÓShea"),
            "john óshea",
        )
        self.assertNotEqual(
            normalise_player_name("John ÓShea"),
            normalise_player_name("John O'Shea"),
        )


if __name__ == "__main__":
    unittest.main()
