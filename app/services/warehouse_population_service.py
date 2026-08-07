from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.historical_import_manager_service import (
    HistoricalImportFolder,
    HistoricalImportLibrary,
    HistoricalImportManagerService,
)


@dataclass(frozen=True)
class WarehousePopulationQueueItem:
    position: int
    folder: Path
    series_label: str
    week_label: str
    group: str
    expected_matches: int
    validated_matches: int
    imported_matches: int
    status: str

    @property
    def remaining_matches(self) -> int:
        return max(
            self.expected_matches - self.imported_matches,
            0,
        )


@dataclass(frozen=True)
class WarehousePopulationPlan:
    root: Path
    library: HistoricalImportLibrary
    queue: Tuple[WarehousePopulationQueueItem, ...]
    blocking_issues: Tuple[str, ...]

    @property
    def discovered_folders(self) -> int:
        return self.library.discovered_count

    @property
    def imported_folders(self) -> int:
        return self.library.imported_count

    @property
    def ready_folders(self) -> int:
        return self.library.ready_count

    @property
    def incomplete_folders(self) -> int:
        return self.library.incomplete_count

    @property
    def partially_imported_folders(self) -> int:
        return self.library.partially_imported_count

    @property
    def error_folders(self) -> int:
        return self.library.error_count

    @property
    def queued_folders(self) -> int:
        return len(self.queue)

    @property
    def expected_matches(self) -> int:
        return sum(
            item.expected_count
            for item in self.library.folders
        )

    @property
    def imported_matches(self) -> int:
        return sum(
            item.imported_count
            for item in self.library.folders
        )

    @property
    def remaining_matches(self) -> int:
        return max(
            self.expected_matches - self.imported_matches,
            0,
        )

    @property
    def coverage_percent(self) -> float:
        if self.expected_matches == 0:
            return 100.0

        return round(
            self.imported_matches
            / self.expected_matches
            * 100,
            2,
        )

    @property
    def complete(self) -> bool:
        return (
            self.queued_folders == 0
            and not self.blocking_issues
        )

    @property
    def blocked(self) -> bool:
        return bool(self.blocking_issues)

    @property
    def next_item(
        self,
    ) -> Optional[WarehousePopulationQueueItem]:
        return self.queue[0] if self.queue else None


class WarehousePopulationService:
    """
    Build a deterministic population plan for a historical MODUS library.

    This service does not write to the warehouse. It scans the complete
    library, compares folders with existing provider mappings, orders ready
    folders, and reports any folders that prevent full population.
    """

    def __init__(
        self,
        *,
        manager_service: Optional[
            HistoricalImportManagerService
        ] = None,
    ) -> None:
        self.manager_service = (
            manager_service
            or HistoricalImportManagerService()
        )

    def build_plan(
        self,
        db: Session,
        *,
        root: str | Path,
    ) -> WarehousePopulationPlan:
        root_path = Path(root).expanduser().resolve()
        library = self.manager_service.scan(
            db,
            root_path,
        )

        ready_folders = sorted(
            (
                item
                for item in library.folders
                if item.status == "ready"
            ),
            key=self._sort_key,
        )

        queue = tuple(
            WarehousePopulationQueueItem(
                position=index,
                folder=item.folder,
                series_label=item.series_label,
                week_label=item.week_label,
                group=item.group,
                expected_matches=item.expected_count,
                validated_matches=item.validated_count,
                imported_matches=item.imported_count,
                status=item.status,
            )
            for index, item in enumerate(
                ready_folders,
                start=1,
            )
        )

        return WarehousePopulationPlan(
            root=root_path,
            library=library,
            queue=queue,
            blocking_issues=self._blocking_issues(
                library.folders
            ),
        )

    @staticmethod
    def _sort_key(
        item: HistoricalImportFolder,
    ) -> tuple:
        manifest = item.manifest

        if manifest is not None:
            series_id = getattr(
                manifest,
                "series_id",
                0,
            ) or 0
            week_id = getattr(
                manifest,
                "week_id",
                0,
            ) or 0
        else:
            series_id = 0
            week_id = 0

        group_order = {
            "Group A": 1,
            "Group B": 2,
            "Group C": 3,
            "Final": 4,
            "Finals": 4,
        }

        return (
            int(series_id),
            int(week_id),
            group_order.get(item.group, 99),
            str(item.folder).casefold(),
        )

    @staticmethod
    def _blocking_issues(
        folders: List[HistoricalImportFolder],
    ) -> Tuple[str, ...]:
        issues = []

        for item in folders:
            if item.status not in {
                "incomplete",
                "partially_imported",
                "error",
            }:
                continue

            detail = item.error_message

            if (
                not detail
                and item.manifest is not None
                and item.manifest.issues
            ):
                detail = "; ".join(
                    issue.message
                    for issue in item.manifest.issues
                )

            if not detail:
                detail = (
                    "Folder requires review before population "
                    "can complete."
                )

            issues.append(
                f"{item.folder}: {detail}"
            )

        return tuple(issues)
