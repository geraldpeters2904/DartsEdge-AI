import unittest
from pathlib import Path


class ForwardScheduleTemplateTests(
    unittest.TestCase
):
    def test_template_contains_forward_schedule_content(
        self,
    ):
        text = Path(
            "app/templates/forward_schedule.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Forward Schedule Discovery",
            text,
        )

        self.assertIn(
            "Current forward fixtures",
            text,
        )


if __name__ == "__main__":
    unittest.main()
