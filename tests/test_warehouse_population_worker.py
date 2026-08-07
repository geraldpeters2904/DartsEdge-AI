import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.warehouse_population_worker import (
    WarehousePopulationWorker,
)


@dataclass
class FakeQueueItem:
    folder: Path
    series_label: str = "Series 14"
    week_label: str = "Week 1"
    group: str = "Group A"


class FakePlan:
    def __init__(
        self,
        *,
        blocked=False,
        complete=False,
        queue=None,
        blocking_issues=(),
        remaining_matches=0,
        coverage_percent=0.0,
    ):
        self.blocked = blocked
        self.complete = complete
        self.queue = tuple(queue or ())
        self.blocking_issues = tuple(
            blocking_issues
        )
        self.remaining_matches = remaining_matches
        self.coverage_percent = coverage_percent

    @property
    def queued_folders(self):
        return len(self.queue)

    @property
    def next_item(self):
        return self.queue[0] if self.queue else None


class FakePopulationService:
    def __init__(self, plans):
        self.plans = list(plans)
        self.calls = []

    def build_plan(self, db, *, root):
        self.calls.append((db, Path(root)))

        if len(self.plans) > 1:
            return self.plans.pop(0)

        return self.plans[0]


@dataclass
class FakeImportResult:
    created_matches: int = 45


class FakeFolderImporter:
    def __init__(self):
        self.calls = []
        self.error = None
        self.result = FakeImportResult()

    def import_folder(self, db, *, folder):
        self.calls.append((db, Path(folder)))

        if self.error:
            raise ValueError(self.error)

        return self.result


class FakeDatabaseSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


class WarehousePopulationWorkerTests(unittest.TestCase):
    def build_worker(self, plans):
        self.population = FakePopulationService(plans)
        self.importer = FakeFolderImporter()
        self.sessions = []

        def create_session():
            session = FakeDatabaseSession()
            self.sessions.append(session)
            return session

        return WarehousePopulationWorker(
            population_service=self.population,
            folder_import_service=self.importer,
            db_session_factory=create_session,
            interval_seconds=0.02,
        )

    def test_worker_imports_queue_until_complete(self):
        folder_a = Path("/tmp/history/Group_A")
        folder_b = Path("/tmp/history/Group_B")

        worker = self.build_worker([
            FakePlan(
                queue=[
                    FakeQueueItem(folder=folder_a),
                    FakeQueueItem(
                        folder=folder_b,
                        group="Group B",
                    ),
                ],
                remaining_matches=90,
                coverage_percent=0.0,
            ),
            FakePlan(
                queue=[
                    FakeQueueItem(
                        folder=folder_b,
                        group="Group B",
                    )
                ],
                remaining_matches=45,
                coverage_percent=50.0,
            ),
            FakePlan(
                queue=[
                    FakeQueueItem(
                        folder=folder_b,
                        group="Group B",
                    )
                ],
                remaining_matches=45,
                coverage_percent=50.0,
            ),
            FakePlan(
                complete=True,
                remaining_matches=0,
                coverage_percent=100.0,
            ),
            FakePlan(
                complete=True,
                remaining_matches=0,
                coverage_percent=100.0,
            ),
        ])

        with tempfile.TemporaryDirectory() as root:
            worker.start(root)
            time.sleep(0.16)
            status = worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(status.imported_folders, 2)
        self.assertEqual(status.imported_matches, 90)
        self.assertEqual(status.last_action, "complete")
        self.assertEqual(status.coverage_percent, 100.0)
        self.assertEqual(len(self.importer.calls), 2)
        self.assertTrue(
            all(session.closed for session in self.sessions)
        )

    def test_worker_stops_when_plan_is_blocked(self):
        worker = self.build_worker([
            FakePlan(
                blocked=True,
                blocking_issues=(
                    "Missing match_100.html.",
                ),
            )
        ])

        with tempfile.TemporaryDirectory() as root:
            worker.start(root)
            time.sleep(0.06)
            status = worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(status.last_action, "blocked")
        self.assertIn(
            "Missing match_100.html.",
            status.last_error,
        )
        self.assertEqual(self.importer.calls, [])

    def test_worker_stops_when_plan_is_complete(self):
        worker = self.build_worker([
            FakePlan(
                complete=True,
                coverage_percent=100.0,
            )
        ])

        with tempfile.TemporaryDirectory() as root:
            worker.start(root)
            time.sleep(0.06)
            status = worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(status.last_action, "complete")
        self.assertEqual(status.coverage_percent, 100.0)

    def test_import_error_rolls_back_and_stops(self):
        folder = Path("/tmp/history/Group_A")
        worker = self.build_worker([
            FakePlan(
                queue=[
                    FakeQueueItem(folder=folder)
                ]
            )
        ])
        self.importer.error = "Commit failed."

        with tempfile.TemporaryDirectory() as root:
            worker.start(root)
            time.sleep(0.06)
            status = worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(status.last_action, "error")
        self.assertEqual(status.last_error, "Commit failed.")
        self.assertTrue(self.sessions[0].rolled_back)
        self.assertTrue(self.sessions[0].closed)

    def test_start_is_idempotent(self):
        folder = Path("/tmp/history/Group_A")
        worker = self.build_worker([
            FakePlan(
                queue=[
                    FakeQueueItem(folder=folder)
                ]
            )
        ])

        with tempfile.TemporaryDirectory() as root:
            first = worker.start(root)
            second = worker.start(root)
            worker.stop(root)

        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(first.started_at, second.started_at)

    def test_stop_marks_worker_stopped(self):
        folder = Path("/tmp/history/Group_A")
        worker = self.build_worker([
            FakePlan(
                queue=[
                    FakeQueueItem(folder=folder)
                ]
            )
        ])

        with tempfile.TemporaryDirectory() as root:
            worker.start(root)
            stopped = worker.stop(root)

        self.assertFalse(stopped.running)
        self.assertIn(
            "stopped",
            stopped.last_message.lower(),
        )


if __name__ == "__main__":
    unittest.main()
