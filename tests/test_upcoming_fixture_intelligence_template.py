import unittest
from pathlib import Path


class UpcomingFixtureIntelligenceTemplateTests(
    unittest.TestCase
):
    def test_core_content_present(
        self,
    ):
        text = Path(
            "app/templates/upcoming_fixture_intelligence.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Upcoming Fixture Intelligence",
            text,
        )

        self.assertIn(
            "historical matches",
            text,
        )

        self.assertIn(
            "Minimum depth",
            text,
        )


if __name__ == "__main__":
    unittest.main()
