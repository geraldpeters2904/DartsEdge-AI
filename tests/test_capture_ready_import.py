import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.incremental_historical_series_pipeline_service import (
    IncrementalHistoricalSeriesPipelineService,
)


ROOT = Path("/tmp/history").resolve()
SERIES_ROOT = ROOT / "Series_14"
FINAL_FOLDER = SERIES_ROOT / "Week_01" / "Final"


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
    def run_cycle(self, *, root, catalog_html):
        return FakePreparation()


@dataclass
class FakeManifest:
    ready: bool = True
    series_label: str = "Series 14"
    week_label: str = "Week 1"
    group: str = "Final"


@dataclass
class FakeFolder:
    folder: Path
    status: str
    manifest: object
    imported_count: int = 3
    error_message: str = None


@dataclass
class FakeLibrary:
    folders: list


class FakeImportManager:
    def scan(self, db, root):
        return FakeLibrary([
            FakeFolder(
                folder=FINAL_FOLDER,
                status="partially_imported",
                manifest=FakeManifest(),
            )
        ])


class FakeCaptureSessionService:
    def next_capture_request(self, folder):
        return None


@dataclass
class FakeImportReport:
    successful: bool = True
    error_message: str = None


class FakeFolderImportService:
    def __init__(self):
        self.calls = []

    def import_folder(self, db, *, folder):
        self.calls.append((db, Path(folder)))
        return FakeImportReport()


class FakeConfigService:
    def load(self, root):
        raise AssertionError(
            "Capture config must not be loaded when importing."
        )


class FakeCaptureExecutor:
    def execute(self, request, *, provider_name):
        raise AssertionError(
            "Capture executor must not run when folder is ready."
        )


class FakeDb:
    def rollback(self):
        pass


class CaptureReadyImportTests(unittest.TestCase):
    def test_ready_partially_imported_folder_imports_immediately(self):
        importer = FakeFolderImportService()

        service = IncrementalHistoricalSeriesPipelineService(
            import_manager=FakeImportManager(),
            preparation_service=FakePreparationService(),
            capture_session_service=FakeCaptureSessionService(),
            capture_executor=FakeCaptureExecutor(),
            capture_config_service=FakeConfigService(),
            folder_import_service=importer,
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "imported")
        self.assertTrue(result.continue_running)
        self.assertEqual(len(importer.calls), 1)
        self.assertEqual(
            importer.calls[0][1],
            FINAL_FOLDER,
        )


if __name__ == "__main__":
    unittest.main()
