import time
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.warehouse_manager_runner import (
    WarehouseManagerRunner,
)


@dataclass
class FakePlan:
    complete_series: int
    remaining_series: int


@dataclass
class FakeSeries:
    series_label: str


@dataclass
class FakeResult:
    action: str
    message: str
    continue_running: bool
    archive_plan: object
    current_series: object = None
    error: str = None


class FakeManager:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.closed = False

    def run_cycle(
        self,
        db,
        *,
        root,
        master_catalog_html,
        watch_folder,
    ):
        self.calls.append(
            (
                db,
                Path(root),
                master_catalog_html,
                watch_folder,
            )
        )

        if len(self.results) > 1:
            return self.results.pop(0)

        return self.results[0]

    def close(self):
        self.closed = True


class FakeProfileCache:
    def __init__(self):
        self.calls = []

    def refresh_players(
        self,
        db,
        *,
        player_ids,
    ):
        self.calls.append(
            (db, list(player_ids))
        )
        return []


class FakeQuery:
    def distinct(self):
        return self

    def all(self):
        return [(1,), (2,)]


class FakeDb:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def query(self, *args):
        return FakeQuery()

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


class WarehouseManagerRunnerTests(unittest.TestCase):
    def build_runner(self, results):
        self.manager = FakeManager(results)
        self.profile_cache = FakeProfileCache()
        self.sessions = []

        def create_session():
            session = FakeDb()
            self.sessions.append(session)
            return session

        return WarehouseManagerRunner(
            manager_service=self.manager,
            profile_cache_service=self.profile_cache,
            db_session_factory=create_session,
            interval_seconds=0.01,
        )

    def test_foreground_runs_until_complete(self):
        runner = self.build_runner([
            FakeResult(
                action="prepared",
                message="Prepared Series 14.",
                continue_running=True,
                archive_plan=FakePlan(0, 14),
                current_series=FakeSeries("Series 14"),
            ),
            FakeResult(
                action="captured",
                message="Captured match.",
                continue_running=True,
                archive_plan=FakePlan(0, 14),
                current_series=FakeSeries("Series 14"),
            ),
            FakeResult(
                action="complete",
                message="Archive complete.",
                continue_running=False,
                archive_plan=FakePlan(14, 0),
            ),
        ])

        status = runner.run_foreground(
            root="/tmp/history",
            master_catalog_html="<html></html>",
        )

        self.assertFalse(status.running)
        self.assertEqual(status.cycles, 3)
        self.assertEqual(status.prepared_cycles, 1)
        self.assertEqual(status.captured_cycles, 1)
        self.assertEqual(status.completed_series, 14)
        self.assertEqual(status.remaining_series, 0)
        self.assertEqual(status.last_action, "complete")
        self.assertTrue(self.manager.closed)
        self.assertTrue(
            all(session.closed for session in self.sessions)
        )

    def test_import_refreshes_player_profiles(self):
        runner = self.build_runner([
            FakeResult(
                action="imported",
                message="Imported Group A.",
                continue_running=True,
                archive_plan=FakePlan(1, 13),
                current_series=FakeSeries("Series 14"),
            ),
            FakeResult(
                action="complete",
                message="Archive complete.",
                continue_running=False,
                archive_plan=FakePlan(14, 0),
            ),
        ])

        status = runner.run_foreground(
            root="/tmp/history",
            master_catalog_html="<html></html>",
        )

        self.assertEqual(status.imported_cycles, 1)
        self.assertEqual(len(self.profile_cache.calls), 1)
        self.assertEqual(
            self.profile_cache.calls[0][1],
            [1, 2],
        )

    def test_background_start_is_idempotent(self):
        runner = self.build_runner([
            FakeResult(
                action="waiting",
                message="Waiting.",
                continue_running=True,
                archive_plan=FakePlan(0, 14),
                current_series=FakeSeries("Series 14"),
            )
        ])

        first = runner.start(
            root="/tmp/history",
            master_catalog_html="<html></html>",
        )
        second = runner.start(
            root="/tmp/history",
            master_catalog_html="<html></html>",
        )

        runner.stop()

        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(first.started_at, second.started_at)

    def test_stop_marks_runner_stopped(self):
        runner = self.build_runner([
            FakeResult(
                action="waiting",
                message="Waiting.",
                continue_running=True,
                archive_plan=FakePlan(0, 14),
                current_series=FakeSeries("Series 14"),
            )
        ])

        runner.start(
            root="/tmp/history",
            master_catalog_html="<html></html>",
        )
        stopped = runner.stop()

        self.assertFalse(stopped.running)
        self.assertIn(
            "stopped",
            stopped.last_message.lower(),
        )


if __name__ == "__main__":
    unittest.main()
