
import unittest
from pathlib import Path


class ForwardScheduleMonitorTemplateTests(unittest.TestCase):
    def test_template_contains_status_fields(self):
        text = Path(
            "app/templates/forward_schedule_monitor.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Forward Schedule Monitor", text)
        self.assertIn("Future fixtures", text)
        self.assertIn("Run discovery now", text)


if __name__ == "__main__":
    unittest.main()
