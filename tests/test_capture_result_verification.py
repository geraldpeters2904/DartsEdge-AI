import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.incremental_historical_series_pipeline_service import (
    IncrementalHistoricalSeriesPipelineService,
)


@dataclass
class FakeTarget:
    series_id: int = 13


@dataclass
class FakePreparation:
    current_target: object = FakeTarget()
    navigation_result: object = None
    batch: object = None
    action: str = "capture_ready"
    message: str = "Ready."

    @property
    def prepared(self):
        return False

    @property
    def complete(self):
        return False


class FakePreparationService:
    def run_cycle(self, *, root, catalog_html):
        return FakePreparation()


@dataclass
class FakeManifest:
    ready: bool = False
    series_label: str = "Series 13"
    week_label: str = "Week 9"
    group: str = "Group C"


@dataclass
class FakeFolder:
    folder: Path
    status: str = "incomplete"
    manifest: object = None
    error_message: str = None


@dataclass
class FakeLibrary:
    folders: list


class FakeImportManager:
    def __init__(self, folder):
        self.folder = folder

    def scan(self, db, root):
        return FakeLibrary([
            FakeFolder(
                folder=self.folder,
                manifest=FakeManifest(),
            )
        ])


@dataclass
class FakeRequest:
    match_id: int
    destination_folder: Path
    destination_filename: str

    @property
    def source_url(self):
        return "https://example.test/match"


class FakeSessionService:
    def __init__(self, request):
        self.request = request

    def next_capture_request(self, folder):
        return self.request

    def refresh_session(self, folder):
        raise AssertionError(
            "Session must not refresh after failed capture."
        )


@dataclass
class FakeCaptureResult:
    successful: bool = False
    waiting: bool = False
    failed: bool = True
    message: str = "Capture validation failed."
    error: str = "No HTML was saved."


class FakeExecutor:
    def execute(self, request, *, provider_name):
        return FakeCaptureResult()


@dataclass
class FakeConfig:
    provider: str = "chrome"


class FakeConfigService:
    def load(self, root):
        return FakeConfig()


class FakeImporter:
    pass


class FakeDb:
    def rollback(self):
        pass


class CaptureResultVerificationTests(unittest.TestCase):
    def test_failed_capture_is_not_reported_as_captured(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            folder = (
                root_path
                / "Series_13"
                / "Week_09"
                / "Group_C"
            )
            folder.mkdir(parents=True)

            request = FakeRequest(
                match_id=16472,
                destination_folder=folder,
                destination_filename="match_16472.html",
            )

            service = IncrementalHistoricalSeriesPipelineService(
                import_manager=FakeImportManager(folder),
                preparation_service=FakePreparationService(),
                capture_session_service=FakeSessionService(
                    request
                ),
                capture_executor=FakeExecutor(),
                capture_config_service=FakeConfigService(),
                folder_import_service=FakeImporter(),
            )

            result = service.run_cycle(
                FakeDb(),
                root=root_path,
                catalog_html="<html></html>",
            )

            self.assertEqual(result.action, "error")
            self.assertFalse(result.continue_running)
            self.assertEqual(
                result.current_match_id,
                16472,
            )
            self.assertIn(
                "No HTML was saved",
                result.error,
            )


if __name__ == "__main__":
    unittest.main()
