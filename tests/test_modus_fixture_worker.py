import time
import unittest
from dataclasses import dataclass

from app.services.modus_fixture_worker import (
    ModusFixtureWorker,
)


@dataclass
class FakeImportResult:
    fixture_count: int


@dataclass
class FakeDiscoveryResult:
    action: str
    message: str
    import_result: object = None

    @property
    def imported(self):
        return self.action == "imported"

    @property
    def unchanged(self):
        return self.action == "unchanged"


class FakeDiscoveryService:
    def __init__(self):
        self.results = [
            FakeDiscoveryResult(
                action="unchanged",
                message="No change.",
            )
        ]
        self.calls = []
        self.error = None

    def discover(
        self,
        db,
        *,
        series_id,
        week_id,
        group,
    ):
        self.calls.append(
            (db, series_id, week_id, group)
        )

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


class ModusFixtureWorkerTests(unittest.TestCase):
    def setUp(self):
        self.discovery = FakeDiscoveryService()
        self.sessions = []

        def create_session():
            session = FakeDatabaseSession()
            self.sessions.append(session)
            return session

        self.worker = ModusFixtureWorker(
            discovery_service=self.discovery,
            db_session_factory=create_session,
            interval_seconds=0.02,
        )

    def tearDown(self):
        for status in list(self.worker._statuses.values()):
            self.worker.stop(
                series_id=status.series_id,
                week_id=status.week_id,
                group=status.group,
            )

    def test_worker_checks_immediately_and_repeats(self):
        status = self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        time.sleep(0.08)

        current = self.worker.status(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertTrue(status.running)
        self.assertGreaterEqual(current.checks, 2)
        self.assertGreaterEqual(
            len(self.discovery.calls),
            2,
        )
        self.assertTrue(
            all(session.closed for session in self.sessions)
        )

    def test_worker_counts_imported_and_unchanged_cycles(self):
        self.discovery.results = [
            FakeDiscoveryResult(
                action="imported",
                message="Imported.",
                import_result=FakeImportResult(
                    fixture_count=3,
                ),
            ),
            FakeDiscoveryResult(
                action="unchanged",
                message="No change.",
            ),
        ]

        self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        time.sleep(0.08)

        status = self.worker.status(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertGreaterEqual(status.imported_cycles, 1)
        self.assertGreaterEqual(status.unchanged_cycles, 1)
        self.assertEqual(status.fixtures_seen, 3)

    def test_start_is_idempotent_for_same_target(self):
        first = self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        second = self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(first.started_at, second.started_at)

    def test_different_groups_have_independent_workers(self):
        first = self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        second = self.worker.start(
            series_id=15,
            week_id=178,
            group="Group B",
        )

        self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group B",
        )

        self.assertNotEqual(first.target, second.target)

    def test_worker_stops_and_rolls_back_on_error(self):
        self.discovery.error = "Safari failed."

        self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )
        time.sleep(0.06)

        status = self.worker.status(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertFalse(status.running)
        self.assertEqual(status.last_error, "Safari failed.")
        self.assertTrue(self.sessions[0].rolled_back)
        self.assertTrue(self.sessions[0].closed)

    def test_stop_marks_worker_stopped(self):
        self.worker.start(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        stopped = self.worker.stop(
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertFalse(stopped.running)
        self.assertIn(
            "stopped",
            stopped.last_message.lower(),
        )

    def test_blank_group_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must not be blank",
        ):
            self.worker.start(
                series_id=15,
                week_id=178,
                group=" ",
            )


if __name__ == "__main__":
    unittest.main()
