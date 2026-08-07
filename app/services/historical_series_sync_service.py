from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.historical_capture_orchestrator_service import (
    HistoricalCaptureOrchestratorResult,
    HistoricalCaptureOrchestratorService,
)
from app.services.modus_historical_series_preparation_service import (
    ModusHistoricalSeriesPreparationResult,
    ModusHistoricalSeriesPreparationService,
)


@dataclass(frozen=True)
class HistoricalSeriesSyncResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    preparation: Optional[
        ModusHistoricalSeriesPreparationResult
    ] = None
    orchestration: Optional[
        HistoricalCaptureOrchestratorResult
    ] = None
    error: Optional[str] = None

    @property
    def complete(self) -> bool:
        return self.action == "complete"

    @property
    def prepared(self) -> bool:
        return self.action == "prepared"

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
            "error",
        }


class HistoricalSeriesSyncService:
    """Run one safe end-to-end sync cycle for one MODUS series."""

    def __init__(
        self,
        *,
        preparation_service: Optional[
            ModusHistoricalSeriesPreparationService
        ] = None,
        orchestrator_service: Optional[
            HistoricalCaptureOrchestratorService
        ] = None,
    ) -> None:
        self.preparation_service = (
            preparation_service
            or ModusHistoricalSeriesPreparationService()
        )
        self.orchestrator_service = (
            orchestrator_service
            or HistoricalCaptureOrchestratorService()
        )

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
        catalog_html: str,
        watch_folder: str = "~/Downloads",
    ) -> HistoricalSeriesSyncResult:
        root_path = Path(root).expanduser().resolve()

        try:
            preparation = self.preparation_service.run_cycle(
                root=root_path,
                catalog_html=catalog_html,
            )

            if preparation.prepared:
                return HistoricalSeriesSyncResult(
                    root=root_path,
                    action="prepared",
                    message=preparation.message,
                    continue_running=True,
                    preparation=preparation,
                )

            orchestration = self.orchestrator_service.run_cycle(
                db,
                root=root_path,
                watch_folder=watch_folder,
            )

            if orchestration.action == "complete":
                if preparation.complete:
                    return HistoricalSeriesSyncResult(
                        root=root_path,
                        action="complete",
                        message=(
                            "The selected MODUS series is fully "
                            "captured, validated and imported."
                        ),
                        continue_running=False,
                        preparation=preparation,
                        orchestration=orchestration,
                    )

                return HistoricalSeriesSyncResult(
                    root=root_path,
                    action="capture_ready",
                    message=preparation.message,
                    continue_running=True,
                    preparation=preparation,
                    orchestration=orchestration,
                )

            action = self._map_action(orchestration.action)

            return HistoricalSeriesSyncResult(
                root=root_path,
                action=action,
                message=orchestration.message,
                continue_running=orchestration.continue_running,
                preparation=preparation,
                orchestration=orchestration,
                error=orchestration.error,
            )

        except Exception as exc:
            rollback = getattr(db, "rollback", None)
            if callable(rollback):
                rollback()

            return HistoricalSeriesSyncResult(
                root=root_path,
                action="error",
                message="Historical series synchronisation failed.",
                continue_running=False,
                error=str(exc),
            )

    @staticmethod
    def _map_action(action: str) -> str:
        clean = str(action or "").strip().casefold()

        if clean in {
            "started",
            "waiting",
            "capture_ready",
            "captured",
            "imported",
            "blocked",
            "paused",
            "failed",
            "error",
        }:
            return clean

        return clean or "unknown"
