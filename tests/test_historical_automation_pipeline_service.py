import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.historical_automation_pipeline_service import (
    HistoricalAutomationPipelineService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakeRunner:
    complete: bool


@dataclass
class FakeWorkflow:
    runner: FakeRunner


@dataclass
class FakeDiscovery:
    root: Path = ROOT
    discovered_session_files: int = 1
    repaired_sessions: int = 0
    untracked_results_folders: int = 0
    issues: list = None


@dataclass
class FakeFolder:
    folder: Path
    status: str


@dataclass
class FakeIssue:
    message: str


class FakeManifest:
    def __init__(
        self,
        *,
        folder,
        ready,
        issues=None,
    ):
        self.folder = Path(folder)
        self.ready = ready
        self.issues = issues or []


class FakeLibrary:
    def __init__(self, folders):
        self.root = ROOT
        self.folders = folders

    @property
    def ready_count(self):
        return sum(
            1
            for item in self.folders
            if item.status == "ready"
        )


class FakeQueue:
    def __init__(self):
        self.items = []


class FakeEngine:
    def __init__(self, *, has_next=True):
        self.next_item = object() if has_next else None


class FakeDiscoveryService:
    def __init__(self):
        self.calls = []

    def discover(self, root, *, repair):
        self.calls.append((Path(root), repair))
        return FakeDiscovery(issues=[])


class FakeWorkflowService:
    def __init__(self, *, complete):
        self.complete = complete
        self.calls = []

    def capture_iteration(self, root):
        self.calls.append(Path(root))
        return FakeWorkflow(
            runner=FakeRunner(
                complete=self.complete,
            )
        )


class FakeImportManager:
    def __init__(self, folders=None):
        self.folders = folders or []
        self.calls = []

    def scan(self, db, root):
        self.calls.append((db, Path(root)))
        return FakeLibrary(self.folders)


class FakeFolderValidator:
    def __init__(self):
        self.manifests = {}
        self.calls = []

    def configure(
        self,
        folder,
        *,
        ready,
        issues=None,
    ):
        self.manifests[str(Path(folder))] = FakeManifest(
            folder=folder,
            ready=ready,
            issues=issues,
        )

    def inspect(self, folder):
        self.calls.append(Path(folder))
        return self.manifests[str(Path(folder))]


class FakeQueueService:
    def __init__(self, *, existing=False):
        self.existing = existing
        self.created = []
        self.load_calls = 0
        self.queue = FakeQueue()

    def load(self, db, root):
        self.load_calls += 1

        if not self.existing:
            raise ValueError("No queue.")

        return self.queue

    def create(self, *, root, selected_folders):
        self.created.append(
            (Path(root), list(selected_folders))
        )
        self.existing = True
        return Path(root) / ".queue.json"


class FakeEngineService:
    def __init__(
        self,
        *,
        existing=False,
        has_next=True,
    ):
        self.existing = existing
        self.engine = FakeEngine(
            has_next=has_next,
        )
        self.started = []
        self.begun = []

    def load(self, db, root):
        if not self.existing:
            raise ValueError("No engine.")

        return self.engine

    def start(self, db, root):
        self.started.append((db, Path(root)))
        self.existing = True
        return self.engine

    def begin_next(self, db, root):
        self.begun.append((db, Path(root)))
        return self.engine


class HistoricalAutomationPipelineServiceTests(
    unittest.TestCase
):
    def make_service(
        self,
        *,
        capture_complete,
        folders=None,
        queue_existing=False,
        engine_existing=False,
        engine_has_next=True,
    ):
        self.discovery = FakeDiscoveryService()
        self.workflow = FakeWorkflowService(
            complete=capture_complete,
        )
        self.manager = FakeImportManager(
            folders=folders,
        )
        self.validator = FakeFolderValidator()
        self.queue = FakeQueueService(
            existing=queue_existing,
        )
        self.engine = FakeEngineService(
            existing=engine_existing,
            has_next=engine_has_next,
        )

        return HistoricalAutomationPipelineService(
            discovery_service=self.discovery,
            workflow_service=self.workflow,
            import_manager=self.manager,
            folder_validator=self.validator,
            import_queue_service=self.queue,
            import_engine_service=self.engine,
        )

    def test_incomplete_capture_stops_before_validation(self):
        service = self.make_service(
            capture_complete=False,
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertEqual(result.action, "capture")
        self.assertFalse(result.capture_complete)
        self.assertTrue(result.validation_passed)
        self.assertEqual(result.folder_manifests, ())
        self.assertEqual(self.validator.calls, [])
        self.assertEqual(self.manager.calls, [])
        self.assertEqual(self.queue.created, [])

    def test_failed_folder_validation_stops_before_queue(self):
        folder = ROOT / "Series_14" / "Week_01" / "Group_A"

        service = self.make_service(
            capture_complete=True,
            folders=[
                FakeFolder(
                    folder=folder,
                    status="incomplete",
                )
            ],
        )
        self.validator.configure(
            folder,
            ready=False,
            issues=[
                FakeIssue(
                    "Missing match_16947.html."
                )
            ],
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertEqual(result.action, "validate")
        self.assertFalse(result.validation_passed)
        self.assertEqual(len(result.folder_manifests), 1)
        self.assertIn(
            "Missing match_16947.html.",
            result.validation_issues[0],
        )
        self.assertEqual(self.queue.created, [])
        self.assertEqual(self.engine.started, [])

    def test_validated_folder_creates_queue_and_starts_engine(self):
        folder = ROOT / "Series_14" / "Week_01" / "Group_A"

        service = self.make_service(
            capture_complete=True,
            folders=[
                FakeFolder(
                    folder=folder,
                    status="ready",
                )
            ],
        )
        self.validator.configure(
            folder,
            ready=True,
        )
        db = object()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertEqual(result.action, "import")
        self.assertTrue(result.validation_passed)
        self.assertEqual(
            self.queue.created,
            [(ROOT, [str(folder)])],
        )
        self.assertEqual(
            self.engine.started,
            [(db, ROOT)],
        )
        self.assertEqual(
            self.engine.begun,
            [(db, ROOT)],
        )

    def test_imported_folders_do_not_require_revalidation(self):
        imported = ROOT / "Series_14" / "Week_01" / "Group_A"

        service = self.make_service(
            capture_complete=True,
            folders=[
                FakeFolder(
                    folder=imported,
                    status="imported",
                )
            ],
            queue_existing=True,
            engine_existing=True,
            engine_has_next=False,
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertEqual(result.action, "complete")
        self.assertTrue(result.validation_passed)
        self.assertEqual(self.validator.calls, [])

    def test_existing_queue_and_engine_are_reused(self):
        folder = ROOT / "Series_14" / "Week_01" / "Group_A"

        service = self.make_service(
            capture_complete=True,
            folders=[
                FakeFolder(
                    folder=folder,
                    status="ready",
                )
            ],
            queue_existing=True,
            engine_existing=True,
        )
        self.validator.configure(
            folder,
            ready=True,
        )
        db = object()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertEqual(result.action, "import")
        self.assertEqual(self.queue.created, [])
        self.assertEqual(self.engine.started, [])
        self.assertEqual(
            self.engine.begun,
            [(db, ROOT)],
        )

    def test_validated_library_without_queue_candidates_requests_review(self):
        service = self.make_service(
            capture_complete=True,
            folders=[],
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertEqual(result.action, "review")
        self.assertTrue(result.validation_passed)
        self.assertIsNone(result.import_queue)
        self.assertEqual(self.engine.started, [])


if __name__ == "__main__":
    unittest.main()
