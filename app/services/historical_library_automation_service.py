from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.automatic_modus_folder_import_service import (
    AutomaticModusFolderImportResult,
    AutomaticModusFolderImportService,
)
from app.services.historical_import_manager_service import (
    HistoricalImportFolder,
    HistoricalImportLibrary,
    HistoricalImportManagerService,
)


@dataclass(frozen=True)
class HistoricalLibraryAutomationResult:
    root: Path
    library: HistoricalImportLibrary
    action: str
    message: str
    imported_folder: Optional[HistoricalImportFolder] = None
    import_result: Optional[
        AutomaticModusFolderImportResult
    ] = None
    blocking_issues: Tuple[str, ...] = ()

    @property
    def completed(self) -> bool:
        return self.action == "complete"

    @property
    def imported(self) -> bool:
        return self.action == "imported"

    @property
    def blocked(self) -> bool:
        return self.action == "blocked"

    @property
    def continue_running(self) -> bool:
        return self.action == "imported"


class HistoricalLibraryAutomationService:
    """
    Import one ready MODUS folder per cycle from a historical library.

    Resumability comes from the existing HistoricalImportManagerService:
    every scan compares folders with warehouse provider mappings, so
    previously imported folders are automatically skipped.
    """

    def __init__(
        self,
        *,
        manager_service: Optional[
            HistoricalImportManagerService
        ] = None,
        folder_import_service: Optional[
            AutomaticModusFolderImportService
        ] = None,
    ) -> None:
        self.manager_service = (
            manager_service
            or HistoricalImportManagerService()
        )
        self.folder_import_service = (
            folder_import_service
            or AutomaticModusFolderImportService()
        )

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
    ) -> HistoricalLibraryAutomationResult:
        root_path = Path(root).expanduser().resolve()
        library = self.manager_service.scan(
            db,
            root_path,
        )

        ready = [
            item
            for item in library.folders
            if item.status == "ready"
        ]

        if ready:
            folder = ready[0]

            import_result = (
                self.folder_import_service.import_folder(
                    db,
                    folder=folder.folder,
                )
            )

            refreshed = self.manager_service.scan(
                db,
                root_path,
            )

            refreshed_folder = self._find_folder(
                refreshed,
                folder.folder,
            )

            if (
                refreshed_folder is None
                or refreshed_folder.status != "imported"
            ):
                raise ValueError(
                    "Warehouse verification did not confirm "
                    f"completion for {folder.folder}."
                )

            remaining_ready = refreshed.ready_count

            return HistoricalLibraryAutomationResult(
                root=root_path,
                library=refreshed,
                action="imported",
                message=(
                    f"Imported {folder.series_label} · "
                    f"{folder.week_label} · {folder.group}. "
                    f"{remaining_ready} ready folder(s) remain."
                ),
                imported_folder=refreshed_folder,
                import_result=import_result,
            )

        blocking = self._blocking_issues(library)

        if blocking:
            return HistoricalLibraryAutomationResult(
                root=root_path,
                library=library,
                action="blocked",
                message=(
                    "No ready folders can be imported because "
                    "the historical library contains incomplete "
                    "or invalid folders."
                ),
                blocking_issues=blocking,
            )

        return HistoricalLibraryAutomationResult(
            root=root_path,
            library=library,
            action="complete",
            message=(
                "Every discovered historical MODUS folder is "
                "already imported."
            ),
        )

    @staticmethod
    def _find_folder(
        library: HistoricalImportLibrary,
        folder: Path,
    ) -> Optional[HistoricalImportFolder]:
        target = folder.resolve()

        return next(
            (
                item
                for item in library.folders
                if item.folder.resolve() == target
            ),
            None,
        )

    @staticmethod
    def _blocking_issues(
        library: HistoricalImportLibrary,
    ) -> Tuple[str, ...]:
        issues = []

        for item in library.folders:
            if item.status not in {
                "incomplete",
                "partially_imported",
                "error",
            }:
                continue

            detail = item.error_message

            if not detail and item.manifest is not None:
                messages = [
                    issue.message
                    for issue in item.manifest.issues
                ]
                detail = "; ".join(messages)

            if not detail:
                detail = (
                    "Folder requires review before automatic import."
                )

            issues.append(
                f"{item.folder}: {detail}"
            )

        return tuple(issues)
