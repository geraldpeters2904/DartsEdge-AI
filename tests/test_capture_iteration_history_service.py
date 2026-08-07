import unittest
from datetime import datetime, timedelta

from app.models.capture_iteration_history import (
    CaptureIterationHistory,
)
from app.services.capture_iteration_history_service import (
    CaptureIterationHistoryService,
)
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)
from tests.helpers.database import create_test_session


class CaptureIterationHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = CaptureIterationHistoryService()

    def tearDown(self):
        self.db.close()

    def make_summary(
        self,
        *,
        status="running",
        matches_captured=1,
        bytes_written=7004,
        captures_waiting=0,
        retries_attempted=0,
        errors=0,
    ):
        started_at = datetime(
            2026,
            8,
            3,
            9,
            5,
            0,
        )

        return CaptureIterationSummary(
            started_at=started_at,
            finished_at=started_at + timedelta(
                seconds=5.4
            ),
            status=status,
            matches_captured=matches_captured,
            bytes_written=bytes_written,
            captures_waiting=captures_waiting,
            retries_attempted=retries_attempted,
            errors=errors,
        )

    def test_records_successful_capture_iteration(self):
        summary = self.make_summary()

        record = self.service.record(
            self.db,
            capture_root="/tmp/history",
            provider="Safari",
            match_id=16958,
            summary=summary,
        )

        self.assertIsNotNone(record.id)
        self.assertEqual(record.capture_root, "/tmp/history")
        self.assertEqual(record.provider, "safari")
        self.assertEqual(record.match_id, 16958)
        self.assertEqual(record.status, "running")
        self.assertEqual(record.matches_captured, 1)
        self.assertEqual(record.bytes_written, 7004)
        self.assertEqual(record.duration_seconds, 5.4)
        self.assertEqual(record.errors, 0)

        stored = (
            self.db.query(CaptureIterationHistory)
            .one()
        )

        self.assertEqual(stored.id, record.id)

    def test_records_failed_capture_iteration(self):
        summary = self.make_summary(
            status="failed",
            matches_captured=0,
            bytes_written=0,
            retries_attempted=3,
            errors=1,
        )

        record = self.service.record(
            self.db,
            capture_root="/tmp/history",
            provider="safari",
            match_id=16958,
            summary=summary,
            error_detail="Provider unavailable.",
        )

        self.assertEqual(record.status, "failed")
        self.assertEqual(record.retries_attempted, 3)
        self.assertEqual(record.errors, 1)
        self.assertEqual(
            record.error_detail,
            "Provider unavailable.",
        )

    def test_recent_returns_latest_records_for_root(self):
        first = self.make_summary(
            bytes_written=1000,
        )
        second = self.make_summary(
            bytes_written=2000,
        )

        self.service.record(
            self.db,
            capture_root="/tmp/history",
            provider="safari",
            match_id=16958,
            summary=first,
        )
        self.service.record(
            self.db,
            capture_root="/tmp/history",
            provider="safari",
            match_id=16959,
            summary=second,
        )
        self.service.record(
            self.db,
            capture_root="/tmp/other",
            provider="manual",
            match_id=20000,
            summary=first,
        )

        records = self.service.recent(
            self.db,
            capture_root="/tmp/history",
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].match_id, 16959)
        self.assertEqual(records[1].match_id, 16958)

    def test_provider_is_required(self):
        with self.assertRaisesRegex(
            ValueError,
            "provider is required",
        ):
            self.service.record(
                self.db,
                capture_root="/tmp/history",
                provider="",
                match_id=16958,
                summary=self.make_summary(),
            )


if __name__ == "__main__":
    unittest.main()
