import unittest
from types import SimpleNamespace
from app.services.player_name_service import normalise_player_name, player_alias_key

class UniversalPlayerNameTests(unittest.TestCase):
    def test_apostrophe_variants(self):
        values = ["John O'Shea", "John O’Shea", "John O´Shea", "John O`Shea"]
        self.assertEqual({normalise_player_name(v) for v in values}, {"john o'shea"})
        self.assertEqual({player_alias_key(v) for v in values}, {"johnoshea"})

    def test_underscore_case_spacing(self):
        self.assertEqual(normalise_player_name("  Keanu   Van_Velzen "), "keanu van velzen")

if __name__ == "__main__":
    unittest.main()
