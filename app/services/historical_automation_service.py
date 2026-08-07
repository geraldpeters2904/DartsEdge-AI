from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.historical_automation_pipeline_service import (
    HistoricalAutomationPipelineService,
    HistoricalAutomationResult as PipelineResult,
)


@dataclass(frozen=True)
class HistoricalAutomationResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    completed: bool
    validation_failed: bool
    error: Optional[str]
    pipeline_result: Optional[PipelineResult] = None


class HistoricalAutomationService:
    """
    Present one stable automation API above the historical pipeline.

    Workers and routes use this service instead of interpreting low-level
    pipeline actions themselves.
    """

    def __init__(
        self,
        *,
        pipeline_service: Optional[
            HistoricalAutomationPipelineService
        ] = None,
    ) -> None:
        self.pipeline_service = (
            pipeline_service
            or HistoricalAutomationPipelineService()
        )

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
    ) -> HistoricalAutomationResult:
        root_path = Path(root).expanduser().resolve()

        try:
            pipeline = self.pipeline_service.run_cycle(
                db,
                root=root_path,
            )
        except Exception as exc:
            return HistoricalAutomationResult(
                root=root_path,
                action="error",
                message="Historical automation cycle failed.",
                continue_running=False,
                completed=False,
                validation_failed=False,
                error=str(exc),
                pipeline_result=None,
            )

        return self._from_pipeline(
            root_path,
            pipeline,
        )

    @staticmethod
    def _from_pipeline(
        root: Path,
        pipeline: PipelineResult,
    ) -> HistoricalAutomationResult:
        action = str(pipeline.action or "").strip().casefold()

        if action == "complete":
            return HistoricalAutomationResult(
                root=root,
                action=action,
                message=pipeline.message,
                continue_running=False,
                completed=True,
                validation_failed=False,
                error=None,
                pipeline_result=pipeline,
            )

        if action == "validate":
            detail = (
                "; ".join(pipeline.validation_issues)
                if pipeline.validation_issues
                else None
            )

            return HistoricalAutomationResult(
                root=root,
                action=action,
                message=pipeline.message,
                continue_running=False,
                completed=False,
                validation_failed=True,
                error=detail,
                pipeline_result=pipeline,
            )

        if action in {
            "capture",
            "import",
        }:
            return HistoricalAutomationResult(
                root=root,
                action=action,
                message=pipeline.message,
                continue_running=True,
                completed=False,
                validation_failed=False,
                error=None,
                pipeline_result=pipeline,
            )

        if action == "review":
            return HistoricalAutomationResult(
                root=root,
                action=action,
                message=pipeline.message,
                continue_running=False,
                completed=False,
                validation_failed=False,
                error=None,
                pipeline_result=pipeline,
            )

        return HistoricalAutomationResult(
            root=root,
            action=action or "unknown",
            message=(
                pipeline.message
                or "Historical automation returned an unknown action."
            ),
            continue_running=False,
            completed=False,
            validation_failed=False,
            error=(
                "Unknown historical automation action: "
                + repr(action)
            ),
            pipeline_result=pipeline,
        )
