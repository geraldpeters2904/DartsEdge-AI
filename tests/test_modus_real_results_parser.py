import unittest
from pathlib import Path

from app.providers.adapters.modus_official.parser import (
    ModusSavedPageParser,
)


FIXTURE = Path(
    "tests/fixtures/modus/"
    "results_series14_week13_group_a_real.html"
)


class ModusRealResultsParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.parser = ModusSavedPageParser()

    def test_parses_selected_page_context(self):
        page = self.parser.parse_results_document(self.html)

        self.assertEqual(page.series_id, 14)
        self.assertEqual(page.series_label, "Series 14")
        self.assertEqual(page.week_id, 177)
        self.assertEqual(page.week_label, "Week 13")
        self.assertEqual(page.group, "Group A")

    def test_parses_all_real_match_cards(self):
        page = self.parser.parse_results_document(self.html)

        self.assertEqual(len(page.matches), 45)
        self.assertEqual(page.matches[0].match_id, 18195)
        self.assertEqual(page.matches[0].match_number, 1)
        self.assertEqual(
            page.matches[0].player_a_name,
            "Derek Coulson",
        )
        self.assertEqual(
            page.matches[0].player_b_name,
            "David Evans",
        )
        self.assertEqual(page.matches[0].player_a_legs, 4)
        self.assertEqual(page.matches[0].player_b_legs, 2)

        self.assertEqual(page.matches[-1].match_id, 18239)
        self.assertEqual(page.matches[-1].match_number, 45)

    def test_match_records_receive_page_context(self):
        page = self.parser.parse_results_document(self.html)
        match = page.matches[10]

        self.assertEqual(match.series_label, "Series 14")
        self.assertEqual(match.week_label, "Week 13")
        self.assertEqual(match.group, "Group A")

    def test_parses_group_table(self):
        page = self.parser.parse_results_document(self.html)

        self.assertEqual(len(page.group_table), 6)

        leader = page.group_table[0]
        self.assertEqual(leader.position, 1)
        self.assertEqual(leader.player_name, "Ashley Coleman")
        self.assertEqual(leader.played, 15)
        self.assertEqual(leader.won, 11)
        self.assertEqual(leader.lost, 4)
        self.assertEqual(leader.leg_difference, 15)
        self.assertEqual(leader.three_dart_average, 90.12)
        self.assertEqual(leader.points, 22)

        last = page.group_table[-1]
        self.assertEqual(last.player_name, "David Evans")
        self.assertEqual(last.leg_difference, -20)

    def test_legacy_list_api_uses_real_parser(self):
        matches = self.parser.parse_results_page(self.html)
        self.assertEqual(len(matches), 45)
        self.assertEqual(matches[0].match_id, 18195)

    def test_missing_selected_series_is_rejected(self):
        import re

        broken, replacements = re.subn(
            r'(value="14"[^>]*?)\s+selected(?=\s*>)',
            r'\1',
            self.html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

        self.assertEqual(
            replacements,
            1,
            "Test fixture did not contain the selected Series 14 option.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "no selected Series",
        ):
            self.parser.parse_results_document(broken)

    def test_missing_fixture_cards_is_rejected(self):
        start = self.html.index('<div class="fixtures-grid"')
        end = self.html.index("</section>", start)
        broken = (
            self.html[:start]
            + '<div class="fixtures-grid"></div>'
            + self.html[end:]
        )

        with self.assertRaisesRegex(
            ValueError,
            "No MODUS fixture cards",
        ):
            self.parser.parse_results_document(broken)


if __name__ == "__main__":
    unittest.main()
