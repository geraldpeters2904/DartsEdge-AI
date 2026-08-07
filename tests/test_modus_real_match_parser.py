import unittest
from datetime import datetime
from pathlib import Path

from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
)


FIXTURE = Path("tests/fixtures/modus/match_18195_real.html")


class ModusRealMatchParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.parser = ModusRealMatchPageParser()

    def test_parses_identity_context_and_score(self):
        match = self.parser.parse(self.html, match_id=18195)
        self.assertEqual(match.match_id, 18195)
        self.assertEqual(match.player_a_name, "Derek Coulson")
        self.assertEqual(match.player_b_name, "David Evans")
        self.assertEqual((match.player_a_legs, match.player_b_legs), (4, 2))
        self.assertEqual(match.series_label, "Series 14")
        self.assertEqual(match.week_label, "Week 13")
        self.assertEqual(match.group, "Group A")
        self.assertEqual(match.played_at, datetime(2026, 7, 20, 9, 42))

    def test_parses_player_a_statistics(self):
        stats = self.parser.parse(self.html, match_id=18195).player_a_stats
        self.assertEqual(stats.three_dart_average, 108.70)
        self.assertEqual(stats.scores_100_plus, 6)
        self.assertEqual(stats.scores_140_plus, 6)
        self.assertEqual(stats.scores_180, 3)
        self.assertEqual(stats.checkouts_completed, 4)
        self.assertEqual(stats.checkout_attempts, 8)
        self.assertEqual(stats.checkout_percentage, 50.0)
        self.assertEqual(stats.highest_checkout, 41)
        self.assertEqual(stats.ton_plus_checkouts, 0)

    def test_parses_player_b_statistics(self):
        stats = self.parser.parse(self.html, match_id=18195).player_b_stats
        self.assertEqual(stats.three_dart_average, 85.56)
        self.assertEqual(stats.scores_100_plus, 10)
        self.assertEqual(stats.scores_140_plus, 1)
        self.assertEqual(stats.scores_180, 0)
        self.assertEqual(stats.checkouts_completed, 2)
        self.assertEqual(stats.checkout_attempts, 3)
        self.assertEqual(stats.checkout_percentage, 66.67)
        self.assertEqual(stats.highest_checkout, 40)
        self.assertEqual(stats.ton_plus_checkouts, 0)

    def test_match_id_is_required(self):
        with self.assertRaisesRegex(ValueError, "Pass match_id explicitly"):
            self.parser.parse(self.html)

    def test_missing_stat_is_rejected(self):
        broken = self.html.replace('<div class="stat-label">180s</div>', '<div class="stat-label">Other</div>', 1)
        with self.assertRaisesRegex(ValueError, "missing statistics: 180s"):
            self.parser.parse(broken, match_id=18195)


    def test_accepts_whole_number_checkout_rounding(self):
        rounded = self.html.replace(
            '<div class="stat-left highlight">4/8</div>',
            '<div class="stat-left highlight">1/19</div>',
            1,
        ).replace(
            '50<small>%</small>',
            '5<small>%</small>',
            1,
        )

        stats = self.parser.parse(
            rounded,
            match_id=18195,
        ).player_a_stats

        self.assertEqual(stats.checkouts_completed, 1)
        self.assertEqual(stats.checkout_attempts, 19)
        self.assertEqual(stats.checkout_percentage, 5.0)


    def test_accepts_whole_number_checkout_truncation(self):
        truncated = self.html.replace(
            '<div class="stat-right ">2/3</div>',
            '<div class="stat-right ">4/6</div>',
            1,
        ).replace(
            '66.67<small>%</small>',
            '66<small>%</small>',
            1,
        )

        stats = self.parser.parse(
            truncated,
            match_id=18195,
        ).player_b_stats

        self.assertEqual(stats.checkouts_completed, 4)
        self.assertEqual(stats.checkout_attempts, 6)
        self.assertEqual(stats.checkout_percentage, 66.0)

    def test_accepts_decimal_checkout_rounding(self):
        stats = self.parser.parse(
            self.html,
            match_id=18195,
        ).player_b_stats

        self.assertEqual(stats.checkouts_completed, 2)
        self.assertEqual(stats.checkout_attempts, 3)
        self.assertEqual(stats.checkout_percentage, 66.67)

    def test_recovers_percentage_outside_display_rounding(self):
        broken = self.html.replace(
            '50<small>%</small>',
            '49<small>%</small>',
            1,
        )

        parsed = self.parser.parse(
            broken,
            match_id=18195,
        )

        self.assertEqual(
            parsed.player_a_stats.checkout_percentage,
            50.0,
        )

    def test_checkout_percentage_uses_fraction_when_page_disagrees(self):
        broken = self.html.replace(
            '50<small>%</small>',
            '40<small>%</small>',
            1,
        )

        parsed = self.parser.parse(
            broken,
            match_id=18195,
        )

        self.assertEqual(
            parsed.player_a_stats.checkout_percentage,
            50.0,
        )


if __name__ == "__main__":
    unittest.main()
