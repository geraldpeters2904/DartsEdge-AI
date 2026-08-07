import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.incremental_historical_series_pipeline_service import (
    IncrementalHistoricalSeriesPipelineService,
)


ROOT = Path("/tmp/history").resolve()
SERIES_ROOT = ROOT / "Series_14"
GROUP_A = SERIES_ROOT / "Week_13" / "Group_A"


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
    ready: bool = False
    series_label: str = "Series 14"
    week_label: str = "Week 13"
    group: str = "Group A"


@dataclass
class FakeFolder:
    folder: Path
    status: str
    manifest: object = None
    imported_count: int = 0
    error_message: str = None


@dataclass
class FakeLibrary:
    folders: list


class FakeImportManager:
    def __init__(self, folders):
        self.folders = folders

    def scan(self, db, root):
        self.root = Path(root)
        return FakeLibrary(self.folders)


@dataclass
class FakeRequest:
    match_id: int = 18195


@dataclass
class FakeSession:
    series_label: str = "Series 14"
    week_label: str = "Week 13"
    group: str = "Group A"


class FakeCaptureSessionService:
    def __init__(self):
        self.requested_folder = None

    def next_capture_request(self, folder):
        self.requested_folder = Path(folder)
        return FakeRequest()

    def refresh_session(self, folder):
        return FakeSession()


@dataclass
class FakeConfig:
    provider: str = "chrome"


class FakeConfigService:
    def load(self, root):
        return FakeConfig()


class FakeCaptureExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, request, *, provider_name):
        self.calls.append((request, provider_name))
        return object()


class FakeImporter:
    def import_folder(self, db, *, folder):
        raise AssertionError(
            "Partially imported incomplete folder "
            "must capture before importing."
        )


class FakeDb:
    def rollback(self):
        pass


class PartialImportResumeTests(unittest.TestCase):
    def test_partially_imported_folder_resumes_capture(self):
        folder = FakeFolder(
            folder=GROUP_A,
            status="partially_imported",
            manifest=FakeManifest(),
            imported_count=3,
        )
        sessions = FakeCaptureSessionService()
        executor = FakeCaptureExecutor()

        service = IncrementalHistoricalSeriesPipelineService(
            import_manager=FakeImportManager([folder]),
            preparation_service=FakePreparationService(),
            capture_session_service=sessions,
            capture_executor=executor,
            capture_config_service=FakeConfigService(),
            folder_import_service=FakeImporter(),
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "captured")
        self.assertEqual(result.current_match_id, 18195)
        self.assertEqual(
            sessions.requested_folder,
            GROUP_A,
        )
        self.assertEqual(
            executor.calls[0][1],
            "chrome",
        )


if __name__ == "__main__":
    unittest.main()
