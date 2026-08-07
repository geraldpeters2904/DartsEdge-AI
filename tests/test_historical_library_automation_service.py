import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.historical_library_automation_service import (
    HistoricalLibraryAutomationService,
)


ROOT = Path("/tmp/history").resolve()
FOLDER_A = ROOT / "Series_14" / "Week_01" / "Group_A"
FOLDER_B = ROOT / "Series_14" / "Week_01" / "Group_B"


@dataclass
class FakeManifestIssue:
    message: str


@dataclass
class FakeManifest:
    issues: list


@dataclass
class FakeFolder:
    folder: Path
    status: str
    series_label: str = "Series 14"
    week_label: str = "Week 1"
    group: str = "Group A"
    error_message: str = None
    manifest: object = None


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


@dataclass
class FakeImportResult:
    batch_id: int = 1
    created_matches: int = 2


class FakeManager:
    def __init__(self, libraries):
        self.libraries = list(libraries)
        self.calls = []

    def scan(self, db, root):
        self.calls.append((db, Path(root)))

        if len(self.libraries) > 1:
            return self.libraries.pop(0)

        return self.libraries[0]


class FakeFolderImporter:
    def __init__(self):
        self.calls = []
        self.result = FakeImportResult()
        self.error = None

    def import_folder(self, db, *, folder):
        self.calls.append((db, Path(folder)))

        if self.error:
            raise ValueError(self.error)

        return self.result


class HistoricalLibraryAutomationServiceTests(
    unittest.TestCase
):
    def build(self, libraries):
        self.manager = FakeManager(libraries)
        self.importer = FakeFolderImporter()

        return HistoricalLibraryAutomationService(
            manager_service=self.manager,
            folder_import_service=self.importer,
        )

    def test_imports_first_ready_folder(self):
        before = FakeLibrary([
            FakeFolder(
                folder=FOLDER_A,
                status="ready",
            ),
            FakeFolder(
                folder=FOLDER_B,
                status="ready",
                group="Group B",
            ),
        ])
        after = FakeLibrary([
            FakeFolder(
                folder=FOLDER_A,
                status="imported",
            ),
            FakeFolder(
                folder=FOLDER_B,
                status="ready",
                group="Group B",
            ),
        ])
        service = self.build([before, after])
        db = object()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertTrue(result.imported)
        self.assertTrue(result.continue_running)
        self.assertEqual(
            self.importer.calls,
            [(db, FOLDER_A)],
        )
        self.assertEqual(
            result.imported_folder.status,
            "imported",
        )
        self.assertIn(
            "1 ready folder(s) remain",
            result.message,
        )

    def test_completed_library_stops(self):
        service = self.build([
            FakeLibrary([
                FakeFolder(
                    folder=FOLDER_A,
                    status="imported",
                )
            ])
        ])

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertTrue(result.completed)
        self.assertFalse(result.continue_running)
        self.assertEqual(self.importer.calls, [])

    def test_incomplete_folder_blocks_when_none_ready(self):
        service = self.build([
            FakeLibrary([
                FakeFolder(
                    folder=FOLDER_A,
                    status="incomplete",
                    manifest=FakeManifest(
                        issues=[
                            FakeManifestIssue(
                                "Missing match_100.html."
                            )
                        ]
                    ),
                )
            ])
        ])

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertTrue(result.blocked)
        self.assertFalse(result.continue_running)
        self.assertIn(
            "Missing match_100.html.",
            result.blocking_issues[0],
        )
        self.assertEqual(self.importer.calls, [])

    def test_error_folder_uses_error_message(self):
        service = self.build([
            FakeLibrary([
                FakeFolder(
                    folder=FOLDER_A,
                    status="error",
                    error_message="Unreadable results page.",
                )
            ])
        ])

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertTrue(result.blocked)
        self.assertIn(
            "Unreadable results page.",
            result.blocking_issues[0],
        )

    def test_import_must_be_confirmed_by_rescan(self):
        before = FakeLibrary([
            FakeFolder(
                folder=FOLDER_A,
                status="ready",
            )
        ])
        after = FakeLibrary([
            FakeFolder(
                folder=FOLDER_A,
                status="ready",
            )
        ])
        service = self.build([before, after])

        with self.assertRaisesRegex(
            ValueError,
            "Warehouse verification",
        ):
            service.run_cycle(
                object(),
                root=ROOT,
            )

    def test_import_error_is_propagated(self):
        service = self.build([
            FakeLibrary([
                FakeFolder(
                    folder=FOLDER_A,
                    status="ready",
                )
            ])
        ])
        self.importer.error = "Commit failed."

        with self.assertRaisesRegex(
            ValueError,
            "Commit failed",
        ):
            service.run_cycle(
                object(),
                root=ROOT,
            )


if __name__ == "__main__":
    unittest.main()
