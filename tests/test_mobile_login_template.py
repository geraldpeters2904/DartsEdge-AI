import unittest
from pathlib import Path


class MobileLoginTemplateTests(
    unittest.TestCase
):
    def test_login_template_contains_form_fields(self):
        text = Path(
            "app/templates/mobile_login.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "DartsEdge Sign In",
            text,
        )
        self.assertIn(
            'name="username"',
            text,
        )
        self.assertIn(
            'name="password"',
            text,
        )
        self.assertIn(
            'action="/mobile-login"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
