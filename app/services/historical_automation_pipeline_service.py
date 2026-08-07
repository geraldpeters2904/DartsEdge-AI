from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.capture_discovery_service import (
    CaptureDiscoveryReport,
    CaptureDiscoveryService,
)
from app.services.historical_import_engine_service import (
    EngineState,
    HistoricalImportEngineService,
)
from app.services.historical_import_manager_service import (
    HistoricalImportLibrary,
    HistoricalImportManagerService,
)
from app.services.historical_import_queue_service import (
    HistoricalImportQueue,
    HistoricalImportQueueService,
)
from app.services.historical_workflow_service import (
    HistoricalWorkflowService,
    HistoricalWorkflowStatus,
)
from app.services.modus_folder_service import (
    ModusFolderImportService,
    ModusFolderManifest,
)


@dataclass(frozen=True)
class HistoricalAutomationResult:
    root: Path
    discovery: CaptureDiscoveryReport
    workflow: HistoricalWorkflowStatus
    import_library: Optional[HistoricalImportLibrary]
    folder_manifests: Tuple[ModusFolderManifest, ...]
    validation_issues: Tuple[str, ...]
    import_queue: Optional[HistoricalImportQueue]
    import_engine: Optional[EngineState]
    action: str
    message: str

    @property
    def capture_complete(self) -> bool:
        return self.workflow.runner.complete

    @property
    def validation_passed(self) -> bool:
        return not self.validation_issues

    @property
    def import_ready(self) -> bool:
        return (
            self.import_library is not None
            and self.import_library.ready_count > 0
            and self.validation_passed
        )


class HistoricalAutomationPipelineService:
    """
    Execute one deterministic historical automation cycle.

    The cycle repairs capture sessions, performs one capture iteration,
    validates completed capture folders, then prepares and advances the
    historical import queue and engine by one safe planning step.
    """

    def __init__(
        self,
        *,
        discovery_service: Optional[
            CaptureDiscoveryService
        ] = None,
        workflow_service: Optional[
            HistoricalWorkflowService
        ] = None,
        import_manager: Optional[
            HistoricalImportManagerService
        ] = None,
        folder_validator: Optional[
            ModusFolderImportService
        ] = None,
        import_queue_service: Optional[
            HistoricalImportQueueService
        ] = None,
        import_engine_service: Optional[
            HistoricalImportEngineService
        ] = None,
    ) -> None:
        self.discovery_service = (
            discovery_service or CaptureDiscoveryService()
        )
        self.workflow_service = (
            workflow_service or HistoricalWorkflowService()
        )
        self.import_manager = (
            import_manager or HistoricalImportManagerService()
        )
        self.folder_validator = (
            folder_validator or ModusFolderImportService()
        )
        self.import_queue_service = (
            import_queue_service
            or HistoricalImportQueueService()
        )
        self.import_engine_service = (
            import_engine_service
            or HistoricalImportEngineService()
        )

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
    ) -> HistoricalAutomationResult:
        root_path = Path(root).expanduser().resolve()

        discovery = self.discovery_service.discover(
            root_path,
            repair=True,
        )

        workflow = self.workflow_service.capture_iteration(
            root_path
        )

        if not workflow.runner.complete:
            return HistoricalAutomationResult(
                root=root_path,
                discovery=discovery,
                workflow=workflow,
                import_library=None,
                folder_manifests=(),
                validation_issues=(),
                import_queue=None,
                import_engine=None,
                action="capture",
                message=(
                    "Capture cycle completed. Historical capture "
                    "is not complete yet."
                ),
            )

        library = self.import_manager.scan(
            db,
            root_path,
        )

        manifests, issues = self._validate_library(
            library
        )

        if issues:
            return HistoricalAutomationResult(
                root=root_path,
                discovery=discovery,
                workflow=workflow,
                import_library=library,
                folder_manifests=manifests,
                validation_issues=issues,
                import_queue=None,
                import_engine=None,
                action="validate",
                message=(
                    "Capture is complete, but one or more folders "
                    "failed validation."
                ),
            )

        queue = self._load_or_create_queue(
            db,
            root_path,
            library,
        )

        if queue is None:
            return HistoricalAutomationResult(
                root=root_path,
                discovery=discovery,
                workflow=workflow,
                import_library=library,
                folder_manifests=manifests,
                validation_issues=(),
                import_queue=None,
                import_engine=None,
                action="review",
                message=(
                    "Capture and folder validation are complete, "
                    "but no folders are available for import."
                ),
            )

        engine = self._load_or_start_engine(
            db,
            root_path,
        )

        if engine.next_item is not None:
            engine = self.import_engine_service.begin_next(
                db,
                root_path,
            )
            action = "import"
            message = (
                "Capture folders passed validation. The next "
                "historical import group is in progress."
            )
        else:
            action = "complete"
            message = (
                "Capture validation and historical import "
                "planning are complete."
            )

        return HistoricalAutomationResult(
            root=root_path,
            discovery=discovery,
            workflow=workflow,
            import_library=library,
            folder_manifests=manifests,
            validation_issues=(),
            import_queue=queue,
            import_engine=engine,
            action=action,
            message=message,
        )

    def _validate_library(
        self,
        library: HistoricalImportLibrary,
    ) -> tuple[
        Tuple[ModusFolderManifest, ...],
        Tuple[str, ...],
    ]:
        manifests = []
        issues = []

        for item in library.folders:
            if item.status == "imported":
                continue

            try:
                manifest = self.folder_validator.inspect(
                    item.folder
                )
                manifests.append(manifest)

                if not manifest.ready:
                    folder_issues = [
                        issue.message
                        for issue in manifest.issues
                    ]

                    if not folder_issues:
                        folder_issues = [
                            "Captured folder is not ready for import."
                        ]

                    issues.extend(
                        f"{item.folder}: {message}"
                        for message in folder_issues
                    )
            except Exception as exc:
                issues.append(
                    f"{item.folder}: {exc}"
                )

        return tuple(manifests), tuple(issues)

    def _load_or_create_queue(
        self,
        db: Session,
        root: Path,
        library: HistoricalImportLibrary,
    ) -> Optional[HistoricalImportQueue]:
        try:
            return self.import_queue_service.load(
                db,
                root,
            )
        except ValueError:
            selected = [
                str(item.folder)
                for item in library.folders
                if item.status in {
                    "ready",
                    "partially_imported",
                    "imported",
                }
            ]

            if not selected:
                return None

            self.import_queue_service.create(
                root=root,
                selected_folders=selected,
            )

            return self.import_queue_service.load(
                db,
                root,
            )

    def _load_or_start_engine(
        self,
        db: Session,
        root: Path,
    ) -> EngineState:
        try:
            return self.import_engine_service.load(
                db,
                root,
            )
        except ValueError:
            return self.import_engine_service.start(
                db,
                root,
            )
