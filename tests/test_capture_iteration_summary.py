import unittest
from datetime import datetime, timedelta

from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)


class CaptureIterationSummaryTests(unittest.TestCase):
    def test_duration_is_none_while_iteration_is_running(self):
        summary = CaptureIterationSummary(
            started_at=datetime(2026, 8, 1, 12, 0, 0),
        )

        self.assertIsNone(summary.duration_seconds)

    def test_duration_is_calculated_after_iteration_finishes(self):
        started_at = datetime(2026, 8, 1, 12, 0, 0)

        summary = CaptureIterationSummary(
            started_at=started_at,
            finished_at=started_at + timedelta(seconds=18.4),
            status="completed",
            matches_captured=24,
            players_discovered=48,
            statistics_written=1152,
            odds_captured=96,
            bytes_written=4096,
            captures_waiting=3,
            retries_attempted=2,
            warnings=2,
        )

        self.assertEqual(summary.duration_seconds, 18.4)
        self.assertEqual(summary.status, "completed")
        self.assertEqual(summary.matches_captured, 24)
        self.assertEqual(summary.bytes_written, 4096)
        self.assertEqual(summary.captures_waiting, 3)
        self.assertEqual(summary.retries_attempted, 2)
        self.assertEqual(summary.warnings, 2)


if __name__ == "__main__":
    unittest.main()
