import unittest
from pathlib import Path


class MobilePairConfirmTests(
    unittest.TestCase
):
    def test_confirmation_template_uses_post(self):
        text = Path(
            "app/templates/mobile_pair_confirm.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Pair this device?",
            text,
        )

        self.assertIn(
            'method="post"',
            text,
        )

        self.assertIn(
            'action="/mobile-pair/{{ token }}"',
            text,
        )

    def test_route_defines_get_preview_and_post_confirm(self):
        text = Path(
            "app/routes/mobile_opportunities.py"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            '@router.get("/mobile-pair/{token}")',
            text,
        )

        self.assertIn(
            '@router.post("/mobile-pair/{token}")',
            text,
        )

        self.assertIn(
            "mobile_pair_preview",
            text,
        )

        self.assertIn(
            "mobile_pair_confirm",
            text,
        )


if __name__ == "__main__":
    unittest.main()
