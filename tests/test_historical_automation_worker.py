import tempfile
import time
import unittest
from dataclasses import dataclass
from typing import Optional

from app.services.historical_automation_worker import (
    HistoricalAutomationWorker,
)


@dataclass
class FakeAutomationResult:
    action: str
    message: str
    continue_running: bool
    error: Optional[str] = None


class FakeAutomationService:
    def __init__(self):
        self.results = [
            FakeAutomationResult(
                action="capture",
                message="Capture continues.",
                continue_running=True,
            )
        ]
        self.calls = []
        self.exception = None

    def run_cycle(self, db, *, root):
        self.calls.append((db, root))

        if self.exception is not None:
            raise ValueError(self.exception)

        if len(self.results) > 1:
            return self.results.pop(0)

        return self.results[0]


class FakeDatabaseSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


class HistoricalAutomationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.automation = FakeAutomationService()
        self.sessions = []

        def create_session():
            session = FakeDatabaseSession()
            self.sessions.append(session)
            return session

        self.worker = HistoricalAutomationWorker(
            automation_service=self.automation,
            db_session_factory=create_session,
            interval_seconds=0.02,
        )

    def tearDown(self):
        for root in list(self.worker._statuses):
            self.worker.stop(root)

    def test_start_runs_background_automation_cycles(self):
        with tempfile.TemporaryDirectory() as root:
            started = self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)
            self.worker.stop(root)

        self.assertTrue(started.running)
        self.assertGreaterEqual(status.cycles, 1)
        self.assertGreaterEqual(
            len(self.automation.calls),
            1,
        )
        self.assertTrue(
            all(session.closed for session in self.sessions)
        )

    def test_start_is_idempotent_for_same_root(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.worker.start(root)
            second = self.worker.start(root)
            self.worker.stop(root)

        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(
            first.started_at,
            second.started_at,
        )

    def test_worker_stops_when_service_says_not_to_continue(self):
        self.automation.results = [
            FakeAutomationResult(
                action="complete",
                message="All work complete.",
                continue_running=False,
            )
        ]

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(
            status.last_action,
            "complete",
        )
        self.assertEqual(
            status.last_message,
            "All work complete.",
        )
        self.assertGreaterEqual(status.cycles, 1)

    def test_worker_propagates_structured_service_error(self):
        self.automation.results = [
            FakeAutomationResult(
                action="validate",
                message="Validation failed.",
                continue_running=False,
                error="Missing match page.",
            )
        ]

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(
            status.last_action,
            "validate",
        )
        self.assertEqual(
            status.last_error,
            "Missing match page.",
        )

    def test_worker_continues_until_service_stops_it(self):
        self.automation.results = [
            FakeAutomationResult(
                action="capture",
                message="Capture continues.",
                continue_running=True,
            ),
            FakeAutomationResult(
                action="import",
                message="Import continues.",
                continue_running=True,
            ),
            FakeAutomationResult(
                action="complete",
                message="Complete.",
                continue_running=False,
            ),
        ]

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.14)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertGreaterEqual(status.cycles, 3)
        self.assertEqual(
            status.last_action,
            "complete",
        )

    def test_worker_records_unexpected_exception(self):
        self.automation.exception = "Automation crashed."

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(
            status.last_error,
            "Automation crashed.",
        )
        self.assertGreaterEqual(len(self.sessions), 1)
        self.assertTrue(self.sessions[0].rolled_back)
        self.assertTrue(self.sessions[0].closed)

    def test_stop_marks_worker_stopped(self):
        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            stopped = self.worker.stop(root)

        self.assertFalse(stopped.running)
        self.assertIn(
            "stopped",
            stopped.last_message.lower(),
        )


if __name__ == "__main__":
    unittest.main()
