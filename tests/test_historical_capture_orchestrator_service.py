import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.historical_capture_orchestrator_service import (
    HistoricalCaptureOrchestratorService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakeRunner:
    status: str
    last_error: str = None

    @property
    def failed(self):
        return self.status == "failed"


@dataclass
class FakeWorkflow:
    status: str
    current_match_id: int = None
    runner: object = None

    def __post_init__(self):
        if self.runner is None:
            self.runner = FakeRunner(self.status)

    @property
    def running(self):
        return self.status == "running"

    @property
    def paused(self):
        return self.status == "paused"

    @property
    def stopped(self):
        return self.status == "stopped"


@dataclass
class FakeSummary:
    matches_captured: int


class FakeWorkflowService:
    def __init__(self, workflow):
        self.workflow = workflow
        self.status_calls = []
        self.start_calls = []
        self.capture_calls = []
        self.summary = FakeSummary(1)

    def status(self, root):
        self.status_calls.append(Path(root))
        return self.workflow

    def start(self, root, *, watch_folder):
        self.start_calls.append(
            (Path(root), watch_folder)
        )
        self.workflow = FakeWorkflow(
            "running",
            current_match_id=100,
        )
        return self.workflow

    def capture_iteration(self, root):
        self.capture_calls.append(Path(root))
        return self.workflow

    def latest_capture_summary(self):
        return self.summary


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
        blocking_issues=(),
        queue=(),
    ):
        self.blocked = blocked
        self.blocking_issues = tuple(
            blocking_issues
        )
        self.queue = tuple(queue)

    @property
    def next_item(self):
        return self.queue[0] if self.queue else None

    @property
    def queued_folders(self):
        return len(self.queue)


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


class FakeImporter:
    def __init__(self):
        self.calls = []
        self.result = FakeImportResult()
        self.error = None

    def import_folder(self, db, *, folder):
        self.calls.append((db, Path(folder)))

        if self.error:
            raise ValueError(self.error)

        return self.result


class FakeDb:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class HistoricalCaptureOrchestratorServiceTests(
    unittest.TestCase
):
    def build(
        self,
        workflow,
        plans=None,
    ):
        self.workflow_service = FakeWorkflowService(
            workflow
        )
        self.population_service = (
            FakePopulationService(
                plans or [FakePlan()]
            )
        )
        self.importer = FakeImporter()

        return HistoricalCaptureOrchestratorService(
            workflow_service=self.workflow_service,
            population_service=self.population_service,
            folder_import_service=self.importer,
        )

    def test_starts_stopped_capture_runner(self):
        service = self.build(
            FakeWorkflow("stopped")
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            watch_folder="~/Downloads",
        )

        self.assertEqual(result.action, "started")
        self.assertTrue(result.continue_running)
        self.assertEqual(
            self.workflow_service.start_calls,
            [(ROOT, "~/Downloads")],
        )

    def test_captures_one_match_per_cycle(self):
        service = self.build(
            FakeWorkflow(
                "running",
                current_match_id=16947,
            )
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
        )

        self.assertTrue(result.captured)
        self.assertTrue(result.continue_running)
        self.assertIn("16947", result.message)
        self.assertEqual(
            self.workflow_service.capture_calls,
            [ROOT],
        )

    def test_paused_capture_stops_safely(self):
        service = self.build(
            FakeWorkflow("paused")
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
        )

        self.assertEqual(result.action, "paused")
        self.assertFalse(result.continue_running)
        self.assertEqual(
            self.population_service.calls,
            [],
        )

    def test_failed_capture_reports_runner_error(self):
        workflow = FakeWorkflow(
            "failed",
            runner=FakeRunner(
                "failed",
                last_error="Safari failed.",
            ),
        )
        service = self.build(workflow)

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
        )

        self.assertEqual(result.action, "failed")
        self.assertEqual(
            result.error,
            "Safari failed.",
        )

    def test_completed_capture_imports_next_folder(self):
        folder = ROOT / "Series_14/Week_01/Group_A"
        service = self.build(
            FakeWorkflow("completed"),
            plans=[
                FakePlan(
                    queue=[
                        FakeQueueItem(folder=folder)
                    ]
                ),
                FakePlan(),
            ],
        )
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertTrue(result.imported)
        self.assertTrue(result.continue_running)
        self.assertEqual(
            self.importer.calls,
            [(db, folder)],
        )
        self.assertEqual(
            result.import_result.created_matches,
            45,
        )

    def test_validation_block_stops_import(self):
        service = self.build(
            FakeWorkflow("completed"),
            plans=[
                FakePlan(
                    blocked=True,
                    blocking_issues=(
                        "Missing match_100.html.",
                    ),
                )
            ],
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
        )

        self.assertTrue(result.blocked)
        self.assertFalse(result.continue_running)
        self.assertIn(
            "Missing match_100.html.",
            result.blocking_issues,
        )
        self.assertEqual(self.importer.calls, [])

    def test_complete_when_capture_and_population_done(self):
        service = self.build(
            FakeWorkflow("completed"),
            plans=[FakePlan()],
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
        )

        self.assertTrue(result.completed)
        self.assertFalse(result.continue_running)

    def test_unexpected_error_rolls_back(self):
        folder = ROOT / "Series_14/Week_01/Group_A"
        service = self.build(
            FakeWorkflow("completed"),
            plans=[
                FakePlan(
                    queue=[
                        FakeQueueItem(folder=folder)
                    ]
                )
            ],
        )
        self.importer.error = "Commit failed."
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertEqual(result.action, "error")
        self.assertEqual(result.error, "Commit failed.")
        self.assertTrue(db.rolled_back)


if __name__ == "__main__":
    unittest.main()
