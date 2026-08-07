from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.automatic_modus_folder_import_service import (
    AutomaticModusFolderImportResult,
    AutomaticModusFolderImportService,
)
from app.services.historical_workflow_service import (
    HistoricalWorkflowService,
    HistoricalWorkflowStatus,
)
from app.services.warehouse_population_service import (
    WarehousePopulationPlan,
    WarehousePopulationService,
)


@dataclass(frozen=True)
class HistoricalCaptureOrchestratorResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    workflow: Optional[HistoricalWorkflowStatus] = None
    population_plan: Optional[WarehousePopulationPlan] = None
    import_result: Optional[
        AutomaticModusFolderImportResult
    ] = None
    blocking_issues: Tuple[str, ...] = ()
    error: Optional[str] = None

    @property
    def completed(self) -> bool:
        return self.action == "complete"

    @property
    def captured(self) -> bool:
        return self.action == "captured"

    @property
    def imported(self) -> bool:
        return self.action == "imported"

    @property
    def blocked(self) -> bool:
        return self.action in {
            "blocked",
            "paused",
            "failed",
        }


class HistoricalCaptureOrchestratorService:
    """
    Coordinate an existing historical capture batch through warehouse import.

    One call performs one safe unit of work:
    - start or advance the existing capture runner;
    - wait safely when capture is paused;
    - validate through the population scanner;
    - import one ready folder through the standard Collector path;
    - stop when the existing library is fully imported.

    Discovery and creation of entirely new Series/Week/Group results pages
    are intentionally outside this service and will feed the capture batch.
    """

    def __init__(
        self,
        *,
        workflow_service: Optional[
            HistoricalWorkflowService
        ] = None,
        population_service: Optional[
            WarehousePopulationService
        ] = None,
        folder_import_service: Optional[
            AutomaticModusFolderImportService
        ] = None,
    ) -> None:
        self.workflow_service = (
            workflow_service or HistoricalWorkflowService()
        )
        self.population_service = (
            population_service
            or WarehousePopulationService()
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
        watch_folder: str = "~/Downloads",
    ) -> HistoricalCaptureOrchestratorResult:
        root_path = Path(root).expanduser().resolve()

        try:
            workflow = self.workflow_service.status(
                root_path
            )

            if workflow.paused:
                return HistoricalCaptureOrchestratorResult(
                    root=root_path,
                    action="paused",
                    message=(
                        "Historical capture is paused and requires "
                        "an explicit resume."
                    ),
                    continue_running=False,
                    workflow=workflow,
                )

            if workflow.runner.failed:
                return HistoricalCaptureOrchestratorResult(
                    root=root_path,
                    action="failed",
                    message="Historical capture runner has failed.",
                    continue_running=False,
                    workflow=workflow,
                    error=workflow.runner.last_error,
                )

            if workflow.stopped:
                workflow = self.workflow_service.start(
                    root_path,
                    watch_folder=watch_folder,
                )

                if workflow.running:
                    return HistoricalCaptureOrchestratorResult(
                        root=root_path,
                        action="started",
                        message=(
                            "Historical capture runner started."
                        ),
                        continue_running=True,
                        workflow=workflow,
                    )

            if workflow.running:
                before_match = workflow.current_match_id
                workflow = (
                    self.workflow_service.capture_iteration(
                        root_path
                    )
                )
                summary = (
                    self.workflow_service
                    .latest_capture_summary()
                )

                captured_count = (
                    summary.matches_captured
                    if summary is not None
                    else 0
                )

                return HistoricalCaptureOrchestratorResult(
                    root=root_path,
                    action=(
                        "captured"
                        if captured_count
                        else "waiting"
                    ),
                    message=(
                        f"Captured match {before_match}."
                        if captured_count
                        else (
                            "Historical capture is waiting for "
                            "the current provider."
                        )
                    ),
                    continue_running=True,
                    workflow=workflow,
                )

            plan = self.population_service.build_plan(
                db,
                root=root_path,
            )

            if plan.blocked:
                return HistoricalCaptureOrchestratorResult(
                    root=root_path,
                    action="blocked",
                    message=(
                        "Capture is complete, but one or more "
                        "folders failed validation or require review."
                    ),
                    continue_running=False,
                    workflow=workflow,
                    population_plan=plan,
                    blocking_issues=plan.blocking_issues,
                )

            if plan.next_item is not None:
                queue_item = plan.next_item
                import_result = (
                    self.folder_import_service.import_folder(
                        db,
                        folder=queue_item.folder,
                    )
                )
                refreshed = (
                    self.population_service.build_plan(
                        db,
                        root=root_path,
                    )
                )

                return HistoricalCaptureOrchestratorResult(
                    root=root_path,
                    action="imported",
                    message=(
                        f"Imported {queue_item.series_label} · "
                        f"{queue_item.week_label} · "
                        f"{queue_item.group}. "
                        f"{refreshed.queued_folders} folder(s) "
                        "remain queued."
                    ),
                    continue_running=True,
                    workflow=workflow,
                    population_plan=refreshed,
                    import_result=import_result,
                )

            return HistoricalCaptureOrchestratorResult(
                root=root_path,
                action="complete",
                message=(
                    "The existing historical capture batch is "
                    "complete and every discovered folder is imported."
                ),
                continue_running=False,
                workflow=workflow,
                population_plan=plan,
            )

        except Exception as exc:
            rollback = getattr(db, "rollback", None)

            if callable(rollback):
                rollback()

            return HistoricalCaptureOrchestratorResult(
                root=root_path,
                action="error",
                message=(
                    "Historical capture orchestration failed."
                ),
                continue_running=False,
                error=str(exc),
            )
