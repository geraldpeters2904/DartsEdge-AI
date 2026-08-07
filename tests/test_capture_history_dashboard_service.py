import unittest
from datetime import datetime, timedelta

from app.services.capture_history_dashboard_service import (
    CaptureHistoryDashboardService,
)
from app.services.capture_iteration_history_service import (
    CaptureIterationHistoryService,
)
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)
from tests.helpers.database import create_test_session


class CaptureHistoryDashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.history = CaptureIterationHistoryService()
        self.service = CaptureHistoryDashboardService()

    def tearDown(self):
        self.db.close()

    def record(
        self,
        *,
        root="/tmp/history",
        match_id=16958,
        status="running",
        matches_captured=0,
        bytes_written=0,
        captures_waiting=0,
        retries_attempted=0,
        errors=0,
        duration_seconds=5.0,
    ):
        started_at = datetime(
            2026,
            8,
            3,
            9,
            0,
            match_id % 60,
        )

        summary = CaptureIterationSummary(
            started_at=started_at,
            finished_at=(
                started_at
                + timedelta(seconds=duration_seconds)
            ),
            status=status,
            matches_captured=matches_captured,
            bytes_written=bytes_written,
            captures_waiting=captures_waiting,
            retries_attempted=retries_attempted,
            errors=errors,
        )

        return self.history.record(
            self.db,
            capture_root=root,
            provider="safari",
            match_id=match_id,
            summary=summary,
            error_detail=(
                "Provider unavailable."
                if errors
                else None
            ),
        )

    def test_builds_empty_dashboard(self):
        dashboard = self.service.build(
            self.db,
            capture_root="/tmp/history",
        )

        self.assertEqual(dashboard.total_iterations, 0)
        self.assertEqual(
            dashboard.successful_iterations,
            0,
        )
        self.assertEqual(dashboard.waiting_iterations, 0)
        self.assertEqual(dashboard.failed_iterations, 0)
        self.assertEqual(
            dashboard.success_rate_percent,
            0.0,
        )
        self.assertEqual(
            dashboard.average_duration_seconds,
            0.0,
        )
        self.assertEqual(dashboard.total_bytes_written, 0)
        self.assertEqual(dashboard.total_retries, 0)
        self.assertEqual(dashboard.recent_records, [])

    def test_builds_capture_history_metrics(self):
        self.record(
            match_id=16958,
            matches_captured=1,
            bytes_written=7000,
            duration_seconds=4.0,
        )
        self.record(
            match_id=16959,
            matches_captured=1,
            bytes_written=9000,
            retries_attempted=1,
            duration_seconds=6.0,
        )
        self.record(
            match_id=16960,
            captures_waiting=1,
            duration_seconds=2.0,
        )
        self.record(
            match_id=16961,
            status="failed",
            retries_attempted=3,
            errors=1,
            duration_seconds=8.0,
        )

        dashboard = self.service.build(
            self.db,
            capture_root="/tmp/history",
        )

        self.assertEqual(dashboard.total_iterations, 4)
        self.assertEqual(
            dashboard.successful_iterations,
            2,
        )
        self.assertEqual(dashboard.waiting_iterations, 1)
        self.assertEqual(dashboard.failed_iterations, 1)
        self.assertEqual(
            dashboard.success_rate_percent,
            50.0,
        )
        self.assertEqual(
            dashboard.average_duration_seconds,
            5.0,
        )
        self.assertEqual(
            dashboard.total_bytes_written,
            16000,
        )
        self.assertEqual(
            dashboard.average_bytes_written,
            4000.0,
        )
        self.assertEqual(dashboard.total_retries, 4)
        self.assertEqual(
            len(dashboard.recent_records),
            4,
        )
        self.assertEqual(
            dashboard.recent_records[0].match_id,
            16961,
        )

    def test_metrics_are_scoped_to_capture_root(self):
        self.record(
            root="/tmp/history",
            match_id=16958,
            matches_captured=1,
            bytes_written=7000,
        )
        self.record(
            root="/tmp/other",
            match_id=20000,
            status="failed",
            errors=1,
        )

        dashboard = self.service.build(
            self.db,
            capture_root="/tmp/history",
        )

        self.assertEqual(dashboard.total_iterations, 1)
        self.assertEqual(
            dashboard.successful_iterations,
            1,
        )
        self.assertEqual(dashboard.failed_iterations, 0)
        self.assertEqual(
            dashboard.total_bytes_written,
            7000,
        )

    def test_recent_limit_is_respected(self):
        for offset in range(5):
            self.record(
                match_id=16958 + offset,
                matches_captured=1,
                bytes_written=1000,
            )

        dashboard = self.service.build(
            self.db,
            capture_root="/tmp/history",
            recent_limit=2,
        )

        self.assertEqual(dashboard.total_iterations, 5)
        self.assertEqual(
            len(dashboard.recent_records),
            2,
        )
        self.assertEqual(
            dashboard.recent_records[0].match_id,
            16962,
        )
        self.assertEqual(
            dashboard.recent_records[1].match_id,
            16961,
        )


if __name__ == "__main__":
    unittest.main()
