import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.modus_capture_session_service import (
    SESSION_FILENAME,
)
from app.services.modus_historical_catalog_service import (
    ModusHistoricalCaptureTarget,
)
from app.services.modus_historical_series_preparation_service import (
    ModusHistoricalSeriesPreparationService,
)


TARGET_A = ModusHistoricalCaptureTarget(
    series_id=14,
    series_label="Series 14",
    week_id=165,
    week_label="Week 1",
    group="Group A",
    source_url="https://example.test/a",
)
TARGET_B = ModusHistoricalCaptureTarget(
    series_id=14,
    series_label="Series 14",
    week_id=165,
    week_label="Week 1",
    group="Group B",
    source_url="https://example.test/b",
)


class FakeCatalogService:
    def targets_for_selected_series(self, html):
        return (TARGET_A, TARGET_B)


@dataclass
class FakeSession:
    destination_folder: Path
    complete: bool
    expected_count: int = 45
    captured_count: int = 0
    missing_count: int = 45


@dataclass
class FakeNavigationResult:
    session: FakeSession


class FakeNavigator:
    def __init__(self):
        self.calls = []
        self.sessions = {}

    def destination_folder(self, *, root, target):
        return (
            Path(root)
            .expanduser()
            .resolve()
            / f"Series_{target.series_id}"
            / "Week_01"
            / target.group.replace(" ", "_")
        )

    def prepare_target(self, *, root, target):
        folder = self.destination_folder(
            root=root,
            target=target,
        )
        folder.mkdir(parents=True, exist_ok=True)
        (folder / SESSION_FILENAME).write_text(
            "{}",
            encoding="utf-8",
        )
        (folder / "results.html").write_text(
            f"<html>{target.group}</html>",
            encoding="utf-8",
        )
        session = FakeSession(
            destination_folder=folder,
            complete=False,
        )
        self.sessions[folder.resolve()] = session
        self.calls.append((Path(root), target))
        return FakeNavigationResult(session=session)


class FakeCaptureSessionService:
    def __init__(self, navigator):
        self.navigator = navigator

    def load_session(self, folder):
        return self.navigator.sessions[
            Path(folder).expanduser().resolve()
        ]


@dataclass
class FakeBatch:
    total_groups: int


class FakeBatchService:
    def __init__(self):
        self.calls = []

    def create(self, *, root, results_pages):
        pages = list(results_pages)
        self.calls.append((Path(root), pages))
        return FakeBatch(total_groups=len(pages))


class ModusHistoricalSeriesPreparationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.navigator = FakeNavigator()
        self.capture = FakeCaptureSessionService(
            self.navigator
        )
        self.batch = FakeBatchService()
        self.service = (
            ModusHistoricalSeriesPreparationService(
                catalog_service=FakeCatalogService(),
                navigator_service=self.navigator,
                capture_session_service=self.capture,
                batch_service=self.batch,
            )
        )

    def test_prepares_first_missing_target(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertTrue(result.prepared)
        self.assertTrue(result.continue_running)
        self.assertEqual(result.current_target, TARGET_A)
        self.assertEqual(result.prepared_targets, 1)
        self.assertEqual(result.completed_targets, 0)
        self.assertEqual(result.remaining_targets, 2)
        self.assertEqual(result.batch.total_groups, 1)

    def test_second_cycle_prepares_next_target(self):
        with tempfile.TemporaryDirectory() as root:
            self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )
            result = self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertTrue(result.prepared)
        self.assertEqual(result.current_target, TARGET_B)
        self.assertEqual(result.prepared_targets, 2)
        self.assertEqual(result.batch.total_groups, 2)

    def test_existing_incomplete_session_is_capture_ready(self):
        with tempfile.TemporaryDirectory() as root:
            for target in (TARGET_A, TARGET_B):
                folder = (
                    self.navigator.destination_folder(
                        root=root,
                        target=target,
                    )
                )
                folder.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                (
                    folder / SESSION_FILENAME
                ).write_text("{}", encoding="utf-8")
                (
                    folder / "results.html"
                ).write_text(
                    "<html></html>",
                    encoding="utf-8",
                )
                self.navigator.sessions[folder.resolve()] = (
                    FakeSession(
                        destination_folder=folder,
                        complete=(
                            target == TARGET_B
                        ),
                    )
                )

            result = self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertTrue(result.capture_ready)
        self.assertEqual(result.current_target, TARGET_A)
        self.assertEqual(result.completed_targets, 1)
        self.assertEqual(result.remaining_targets, 1)

    def test_all_complete_sessions_finish_preparation(self):
        with tempfile.TemporaryDirectory() as root:
            for target in (TARGET_A, TARGET_B):
                folder = (
                    self.navigator.destination_folder(
                        root=root,
                        target=target,
                    )
                )
                folder.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                (
                    folder / SESSION_FILENAME
                ).write_text("{}", encoding="utf-8")
                (
                    folder / "results.html"
                ).write_text(
                    "<html></html>",
                    encoding="utf-8",
                )
                self.navigator.sessions[folder.resolve()] = (
                    FakeSession(
                        destination_folder=folder,
                        complete=True,
                    )
                )

            result = self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertTrue(result.complete)
        self.assertFalse(result.continue_running)
        self.assertEqual(result.completed_targets, 2)
        self.assertEqual(result.remaining_targets, 0)

    def test_batch_contains_every_prepared_page(self):
        with tempfile.TemporaryDirectory() as root:
            self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )
            self.service.run_cycle(
                root=root,
                catalog_html="<html></html>",
            )

        _, pages = self.batch.calls[-1]
        self.assertEqual(len(pages), 2)
        self.assertIn("group_a", pages[0][0])
        self.assertIn("group_b", pages[1][0])


if __name__ == "__main__":
    unittest.main()
