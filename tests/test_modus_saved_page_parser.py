import unittest
from pathlib import Path

from app.providers.adapters.modus_official.parser import ModusSavedPageParser


FIXTURE_DIR = Path("tests/fixtures/modus")


class ModusSavedPageParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = ModusSavedPageParser()

    def read(self, name):
        return (FIXTURE_DIR / name).read_text(encoding="utf-8")

    def test_discovers_both_match_link_patterns(self):
        ids = self.parser.discover_match_ids(
            self.read("results_group_a.html")
        )
        self.assertEqual(ids, [18195, 18196])

    def test_parses_saved_results_cards(self):
        rows = self.parser.parse_results_page(
            self.read("results_group_a.html")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].player_a_name, "Derek Coulson")
        self.assertEqual(rows[0].player_a_legs, 4)
        self.assertIsNone(rows[1].player_a_legs)

    def test_parses_match_level_statistics(self):
        match = self.parser.parse_match_detail(
            self.read("match_18195.html")
        )
        self.assertEqual(match.match_id, 18195)
        self.assertEqual(match.player_a_legs, 4)
        self.assertEqual(
            match.player_a_stats.three_dart_average,
            94.10,
        )
        self.assertEqual(match.player_a_stats.scores_180, 2)
        self.assertEqual(
            match.player_a_stats.checkout_percentage,
            40.0,
        )
        self.assertEqual(
            match.player_a_stats.highest_checkout,
            121,
        )

    def test_missing_required_markers_are_rejected(self):
        with self.assertRaises(ValueError):
            self.parser.parse_match_detail("<html></html>")


if __name__ == "__main__":
    unittest.main()
