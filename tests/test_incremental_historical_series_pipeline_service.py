import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.incremental_historical_series_pipeline_service import (
    IncrementalHistoricalSeriesPipelineService,
)


ROOT = Path("/tmp/history").resolve()
SERIES_ROOT = ROOT / "Series_14"
GROUP_A = SERIES_ROOT / "Week_01" / "Group_A"


@dataclass
class FakeTarget:
    series_id: int = 14


@dataclass
class FakePreparation:
    action: str = "capture_ready"
    message: str = "Ready."
    current_target: object = FakeTarget()
    navigation_result: object = None
    batch: object = None

    @property
    def prepared(self):
        return self.action == "prepared"

    @property
    def complete(self):
        return self.action == "complete"


class FakePreparationService:
    def __init__(self):
        self.result = FakePreparation()

    def run_cycle(self, *, root, catalog_html):
        return self.result


@dataclass
class FakeManifest:
    ready: bool = False
    series_label: str = "Series 14"
    week_label: str = "Week 1"
    group: str = "Group A"


@dataclass
class FakeFolder:
    folder: Path
    status: str
    manifest: object = None
    error_message: str = None


@dataclass
class FakeLibrary:
    folders: list


class FakeImportManager:
    def __init__(self):
        self.folders = []

    def scan(self, db, root):
        if Path(root) != SERIES_ROOT:
            raise AssertionError(
                "Pipeline must scan only the selected series."
            )
        return FakeLibrary(self.folders)


@dataclass
class FakeRequest:
    match_id: int = 17007
    destination_folder: Path = GROUP_A
    destination_filename: str = "match_17007.html"


@dataclass
class FakeSession:
    series_label: str = "Series 14"
    week_label: str = "Week 1"
    group: str = "Group A"
    next_item: object = None


class FakeCaptureSessionService:
    def __init__(self):
        self.request = FakeRequest()

    def next_capture_request(self, folder):
        return self.request

    def refresh_session(self, folder):
        return FakeSession()


@dataclass
class FakeConfig:
    provider: str = "chrome"


class FakeConfigService:
    def load(self, root):
        return FakeConfig()


@dataclass
class FakeCaptureResult:
    successful: bool = True
    waiting: bool = False
    failed: bool = False
    message: str = "Captured."
    error: str = None


class FakeCaptureExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, request, *, provider_name):
        self.calls.append((request, provider_name))

        request.destination_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        (
            request.destination_folder
            / request.destination_filename
        ).write_text(
            "<html></html>",
            encoding="utf-8",
        )

        return FakeCaptureResult()


@dataclass
class FakeImportReport:
    successful: bool = True
    error_message: str = None


class FakeFolderImportService:
    def __init__(self):
        self.calls = []
        self.report = FakeImportReport()

    def import_folder(self, db, *, folder):
        self.calls.append((db, Path(folder)))
        return self.report


class FakeDb:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class IncrementalHistoricalSeriesPipelineTests(
    unittest.TestCase
):
    def setUp(self):
        self.preparation = FakePreparationService()
        self.manager = FakeImportManager()
        self.sessions = FakeCaptureSessionService()
        self.executor = FakeCaptureExecutor()
        self.importer = FakeFolderImportService()
        self.service = (
            IncrementalHistoricalSeriesPipelineService(
                import_manager=self.manager,
                preparation_service=self.preparation,
                capture_session_service=self.sessions,
                capture_executor=self.executor,
                capture_config_service=FakeConfigService(),
                folder_import_service=self.importer,
            )
        )

    def test_ready_group_imports_before_future_incomplete_groups(self):
        ready = FakeFolder(
            GROUP_A,
            "ready",
            FakeManifest(ready=True),
        )
        future = FakeFolder(
            SERIES_ROOT / "Week_02" / "Group_A",
            "incomplete",
            FakeManifest(),
        )
        self.manager.folders = [ready, future]

        result = self.service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "imported")
        self.assertTrue(result.continue_running)
        self.assertEqual(len(self.importer.calls), 1)
        self.assertEqual(self.executor.calls, [])

    def test_incomplete_group_captures_one_match(self):
        self.manager.folders = [
            FakeFolder(
                GROUP_A,
                "incomplete",
                FakeManifest(),
            )
        ]

        result = self.service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "captured")
        self.assertEqual(result.current_match_id, 17007)
        self.assertEqual(
            self.executor.calls[0][1],
            "chrome",
        )

    def test_invalid_group_blocks(self):
        self.manager.folders = [
            FakeFolder(
                GROUP_A,
                "error",
                None,
                "Parser error.",
            )
        ]

        result = self.service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.blocked)
        self.assertEqual(result.error, "Parser error.")

    def test_prepared_group_is_reported_when_library_empty(self):
        self.manager.folders = []
        self.preparation.result = FakePreparation(
            action="prepared",
            message="Prepared Group B.",
        )

        result = self.service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "prepared")
        self.assertTrue(result.continue_running)

    def test_complete_series_stops(self):
        self.manager.folders = []
        self.preparation.result = FakePreparation(
            action="complete",
            message="Complete.",
        )

        result = self.service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.complete)
        self.assertFalse(result.continue_running)


if __name__ == "__main__":
    unittest.main()
