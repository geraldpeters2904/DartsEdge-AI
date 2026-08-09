import unittest
from pathlib import Path


class ForwardFixtureCatchupTemplateTests(
    unittest.TestCase
):
    def test_template_contains_expected_panels(
        self,
    ):
        text = Path(
            "app/templates/forward_fixture_catchup.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Forward Fixture Catch-Up",
            text,
        )

        self.assertIn(
            "Refresh readiness",
            text,
        )

        self.assertIn(
            "Stale scheduled fixtures",
            text,
        )


if __name__ == "__main__":
    unittest.main()
