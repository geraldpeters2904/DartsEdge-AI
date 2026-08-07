import re
import unittest
from pathlib import Path

from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
)


FIXTURE = Path(
    "tests/fixtures/modus/match_18195_real.html"
)


class ModusOptionalGroupParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def test_group_label_is_optional(self):
        html, replacements = re.subn(
            r'<a[^>]*class="[^"]*\btab\b[^"]*"[^>]*>'
            r'\s*Group\s+A\s*</a>',
            "",
            self.html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        self.assertGreaterEqual(
            replacements,
            1,
            "No Group A tab was removed from the fixture.",
        )

        self.assertNotRegex(
            html,
            r'<a[^>]*class="[^"]*\btab\b[^"]*"[^>]*>'
            r'\s*Group\s+A\s*</a>',
        )

        match = ModusRealMatchPageParser().parse(
            html,
            match_id=18195,
        )

        self.assertIsNone(match.group)
        self.assertEqual(
            match.player_a_name,
            "Derek Coulson",
        )
        self.assertEqual(
            match.player_b_name,
            "David Evans",
        )


if __name__ == "__main__":
    unittest.main()
