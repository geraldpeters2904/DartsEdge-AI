import tempfile
import time
import unittest
from dataclasses import dataclass, field

from app.services.historical_library_worker import (
    HistoricalLibraryWorker,
)


@dataclass
class FakeLibraryResult:
    action: str
    message: str
    continue_running: bool
    imported: bool = False
    blocked: bool = False
    blocking_issues: tuple = field(default_factory=tuple)


class FakeAutomationService:
    def __init__(self):
        self.results = [
            FakeLibraryResult(
                action="complete",
                message="Complete.",
                continue_running=False,
            )
        ]
        self.calls = []
        self.error = None

    def run_cycle(self, db, *, root):
        self.calls.append((db, root))

        if self.error:
            raise ValueError(self.error)

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


class HistoricalLibraryWorkerTests(unittest.TestCase):
    def setUp(self):
        self.automation = FakeAutomationService()
        self.sessions = []

        def create_session():
            session = FakeDatabaseSession()
            self.sessions.append(session)
            return session

        self.worker = HistoricalLibraryWorker(
            automation_service=self.automation,
            db_session_factory=create_session,
            interval_seconds=0.02,
        )

    def tearDown(self):
        for root in list(self.worker._statuses):
            self.worker.stop(root)

    def test_worker_imports_until_complete(self):
        self.automation.results = [
            FakeLibraryResult(
                action="imported",
                message="Imported Group A.",
                continue_running=True,
                imported=True,
            ),
            FakeLibraryResult(
                action="imported",
                message="Imported Group B.",
                continue_running=True,
                imported=True,
            ),
            FakeLibraryResult(
                action="complete",
                message="Everything imported.",
                continue_running=False,
            ),
        ]

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.14)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertGreaterEqual(status.cycles, 3)
        self.assertEqual(status.imported_folders, 2)
        self.assertEqual(status.last_action, "complete")
        self.assertEqual(
            status.last_message,
            "Everything imported.",
        )
        self.assertTrue(
            all(session.closed for session in self.sessions)
        )

    def test_worker_stops_when_library_is_blocked(self):
        self.automation.results = [
            FakeLibraryResult(
                action="blocked",
                message="Library blocked.",
                continue_running=False,
                blocked=True,
                blocking_issues=(
                    "Missing match_100.html.",
                ),
            )
        ]

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(status.last_action, "blocked")
        self.assertEqual(
            status.last_error,
            "Missing match_100.html.",
        )

    def test_worker_records_unexpected_error(self):
        self.automation.error = "Import crashed."

        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(
            status.last_error,
            "Import crashed.",
        )
        self.assertTrue(self.sessions[0].rolled_back)
        self.assertTrue(self.sessions[0].closed)

    def test_start_is_idempotent(self):
        self.automation.results = [
            FakeLibraryResult(
                action="imported",
                message="Importing.",
                continue_running=True,
                imported=True,
            )
        ]

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

    def test_stop_marks_worker_stopped(self):
        self.automation.results = [
            FakeLibraryResult(
                action="imported",
                message="Importing.",
                continue_running=True,
                imported=True,
            )
        ]

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
