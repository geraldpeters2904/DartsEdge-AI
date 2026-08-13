import unittest
from pathlib import Path


class MobileLayoutTests(unittest.TestCase):
    def test_mobile_base_has_no_desktop_sidebar(self):
        text = Path(
            "app/templates/mobile_base.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            'class="mobile-app"',
            text,
        )
        self.assertIn(
            "/mobile-logout",
            text,
        )
        self.assertNotIn(
            'class="sidebar"',
            text,
        )
        self.assertNotIn(
            "Command centre",
            text,
        )

    def test_mobile_opportunities_uses_mobile_base(self):
        text = Path(
            "app/templates/mobile_opportunities.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '{% extends "mobile_base.html" %}',
            text,
        )
        self.assertNotIn(
            '{% extends "base.html" %}',
            text,
        )

    def test_login_and_pairing_use_mobile_base(self):
        for path in (
            "app/templates/mobile_login.html",
            "app/templates/mobile_pairing.html",
        ):
            text = Path(path).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                '{% extends "mobile_base.html" %}',
                text,
            )


if __name__ == "__main__":
    unittest.main()
