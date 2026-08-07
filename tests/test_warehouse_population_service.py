import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.warehouse_population_service import (
    WarehousePopulationService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakeIssue:
    message: str


@dataclass
class FakeManifest:
    expected_match_ids: list
    validated_match_ids: list
    missing_match_ids: list
    series_id: int = 14
    week_id: int = 1
    issues: list = None


@dataclass
class FakeFolder:
    folder: Path
    status: str
    imported_count: int
    manifest: object
    series_label: str
    week_label: str
    group: str
    error_message: str = None

    @property
    def expected_count(self):
        return len(self.manifest.expected_match_ids)

    @property
    def validated_count(self):
        return len(self.manifest.validated_match_ids)


class FakeLibrary:
    def __init__(self, folders):
        self.root = ROOT
        self.folders = folders

    @property
    def discovered_count(self):
        return len(self.folders)

    @property
    def ready_count(self):
        return sum(
            1 for item in self.folders
            if item.status == "ready"
        )

    @property
    def incomplete_count(self):
        return sum(
            1 for item in self.folders
            if item.status == "incomplete"
        )

    @property
    def imported_count(self):
        return sum(
            1 for item in self.folders
            if item.status == "imported"
        )

    @property
    def partially_imported_count(self):
        return sum(
            1 for item in self.folders
            if item.status == "partially_imported"
        )

    @property
    def error_count(self):
        return sum(
            1 for item in self.folders
            if item.status == "error"
        )


class FakeManager:
    def __init__(self, library):
        self.library = library
        self.calls = []

    def scan(self, db, root):
        self.calls.append((db, Path(root)))
        return self.library


class WarehousePopulationServiceTests(unittest.TestCase):
    def make_folder(
        self,
        *,
        name,
        status,
        series_id=14,
        week_id=1,
        group="Group A",
        expected=45,
        validated=45,
        imported=0,
        error_message=None,
        issues=None,
    ):
        return FakeFolder(
            folder=ROOT / name,
            status=status,
            imported_count=imported,
            manifest=FakeManifest(
                expected_match_ids=list(range(expected)),
                validated_match_ids=list(range(validated)),
                missing_match_ids=list(
                    range(expected - validated)
                ),
                series_id=series_id,
                week_id=week_id,
                issues=issues or [],
            ),
            series_label=f"Series {series_id}",
            week_label=f"Week {week_id}",
            group=group,
            error_message=error_message,
        )

    def build_service(self, folders):
        self.manager = FakeManager(
            FakeLibrary(folders)
        )
        return WarehousePopulationService(
            manager_service=self.manager,
        )

    def test_builds_ordered_ready_queue(self):
        folders = [
            self.make_folder(
                name="Series_15/Week_02/Group_B",
                status="ready",
                series_id=15,
                week_id=2,
                group="Group B",
            ),
            self.make_folder(
                name="Series_14/Week_01/Group_C",
                status="ready",
                series_id=14,
                week_id=1,
                group="Group C",
            ),
            self.make_folder(
                name="Series_14/Week_01/Group_A",
                status="ready",
                series_id=14,
                week_id=1,
                group="Group A",
            ),
        ]
        service = self.build_service(folders)

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertEqual(plan.queued_folders, 3)
        self.assertEqual(
            [item.group for item in plan.queue],
            ["Group A", "Group C", "Group B"],
        )
        self.assertEqual(
            [item.position for item in plan.queue],
            [1, 2, 3],
        )

    def test_imported_folders_are_not_queued(self):
        service = self.build_service([
            self.make_folder(
                name="Group_A",
                status="imported",
                imported=45,
            ),
            self.make_folder(
                name="Group_B",
                status="ready",
                group="Group B",
            ),
        ])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertEqual(plan.imported_folders, 1)
        self.assertEqual(plan.queued_folders, 1)
        self.assertEqual(
            plan.next_item.group,
            "Group B",
        )

    def test_reports_match_progress_and_coverage(self):
        service = self.build_service([
            self.make_folder(
                name="Group_A",
                status="imported",
                imported=45,
            ),
            self.make_folder(
                name="Group_B",
                status="ready",
                group="Group B",
                imported=0,
            ),
        ])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertEqual(plan.expected_matches, 90)
        self.assertEqual(plan.imported_matches, 45)
        self.assertEqual(plan.remaining_matches, 45)
        self.assertEqual(plan.coverage_percent, 50.0)

    def test_incomplete_folder_creates_blocking_issue(self):
        service = self.build_service([
            self.make_folder(
                name="Group_A",
                status="incomplete",
                validated=44,
                issues=[
                    FakeIssue(
                        "Missing match_100.html."
                    )
                ],
            )
        ])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertTrue(plan.blocked)
        self.assertFalse(plan.complete)
        self.assertIn(
            "Missing match_100.html.",
            plan.blocking_issues[0],
        )

    def test_partially_imported_folder_is_blocking(self):
        service = self.build_service([
            self.make_folder(
                name="Group_A",
                status="partially_imported",
                imported=20,
            )
        ])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertTrue(plan.blocked)
        self.assertEqual(
            plan.partially_imported_folders,
            1,
        )

    def test_fully_imported_library_is_complete(self):
        service = self.build_service([
            self.make_folder(
                name="Group_A",
                status="imported",
                imported=45,
            )
        ])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertTrue(plan.complete)
        self.assertFalse(plan.blocked)
        self.assertEqual(plan.queued_folders, 0)
        self.assertEqual(plan.coverage_percent, 100.0)

    def test_empty_library_is_complete(self):
        service = self.build_service([])

        plan = service.build_plan(
            object(),
            root=ROOT,
        )

        self.assertTrue(plan.complete)
        self.assertEqual(plan.coverage_percent, 100.0)


if __name__ == "__main__":
    unittest.main()
