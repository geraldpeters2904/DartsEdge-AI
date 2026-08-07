from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.services.historical_archive_plan_service import (
    HistoricalArchivePlan,
    HistoricalArchivePlanService,
    HistoricalArchiveSeriesItem,
)
from app.services.incremental_historical_series_pipeline_service import (
    IncrementalHistoricalSeriesPipelineResult,
    IncrementalHistoricalSeriesPipelineService,
)
from app.services.modus_historical_catalog_service import ModusHistoricalCatalogService
from app.services.chrome_browser_session import ChromeBrowserSession
from app.services.prediction_settlement_service import (
    settle_completed_prediction_audits,
)


@dataclass(frozen=True)
class WarehouseManagerResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    archive_plan: Optional[HistoricalArchivePlan] = None
    current_series: Optional[HistoricalArchiveSeriesItem] = None
    series_sync: Optional[IncrementalHistoricalSeriesPipelineResult] = None
    error: Optional[str] = None
    prediction_settlements: int = 0
    prediction_settlement_error: Optional[str] = None

    @property
    def complete(self) -> bool:
        return self.action == "complete"

    @property
    def blocked(self) -> bool:
        return self.action in {"blocked", "paused", "failed", "error"}


class WarehouseManagerService:
    def __init__(
        self,
        *,
        archive_plan_service: Optional[HistoricalArchivePlanService] = None,
        series_sync_service: Optional[IncrementalHistoricalSeriesPipelineService] = None,
        catalog_service: Optional[ModusHistoricalCatalogService] = None,
        browser_session: Optional[ChromeBrowserSession] = None,
        url_model: Optional[ModusUrlModel] = None,
        settlement_runner: Optional[Callable] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.archive_plan_service = archive_plan_service or HistoricalArchivePlanService()
        self.series_sync_service = series_sync_service or IncrementalHistoricalSeriesPipelineService()
        self.catalog_service = catalog_service or ModusHistoricalCatalogService()
        self.browser_session = browser_session or ChromeBrowserSession()
        self.url_model = url_model or ModusUrlModel()
        self.settlement_runner = settlement_runner or settle_completed_prediction_audits
        self.timeout_seconds = float(timeout_seconds)

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
        master_catalog_html: str,
        watch_folder: str = "~/Downloads",
    ) -> WarehouseManagerResult:
        root_path = Path(root).expanduser().resolve()

        try:
            plan = self.archive_plan_service.build_plan(
                root=root_path,
                catalog_html=master_catalog_html,
            )

            if plan.complete:
                settled, settlement_error = self._settle_predictions(db)
                return WarehouseManagerResult(
                    root=root_path,
                    action="complete",
                    message=(
                        "Every MODUS series in the archive catalogue "
                        "is fully captured and imported."
                    ),
                    continue_running=False,
                    archive_plan=plan,
                    prediction_settlements=settled,
                    prediction_settlement_error=settlement_error,
                )

            current = plan.next_series
            if current is None:
                raise ValueError(
                    "Archive plan is incomplete but has no next series."
                )

            catalog = self.catalog_service.parse(master_catalog_html)

            if not catalog.weeks:
                raise ValueError("The MODUS master catalogue has no weeks.")
            if not catalog.groups:
                raise ValueError("The MODUS master catalogue has no groups.")

            probe_week = catalog.weeks[0]
            probe_group = catalog.groups[0]
            source_url = self.url_model.results_url(
                series_id=current.series_id,
                week_id=probe_week.value,
                group=probe_group,
            )

            self.browser_session.goto(
                source_url,
                timeout_seconds=self.timeout_seconds,
            )

            self.browser_session.wait_for(
                lambda: self._series_loaded(current.series_id),
                timeout_seconds=self.timeout_seconds,
                description=f"MODUS {current.series_label} catalogue",
            )

            series_catalog_html = self.browser_session.html()

            sync = self.series_sync_service.run_cycle(
                db,
                root=root_path,
                catalog_html=series_catalog_html,
                watch_folder=watch_folder,
            )

            settled, settlement_error = self._settle_predictions(db)

            return WarehouseManagerResult(
                root=root_path,
                action=sync.action,
                message=f"{current.series_label}: {sync.message}",
                continue_running=sync.continue_running,
                archive_plan=plan,
                current_series=current,
                series_sync=sync,
                error=sync.error,
                prediction_settlements=settled,
                prediction_settlement_error=settlement_error,
            )

        except Exception as exc:
            rollback = getattr(db, "rollback", None)
            if callable(rollback):
                rollback()

            return WarehouseManagerResult(
                root=root_path,
                action="error",
                message="Warehouse manager cycle failed.",
                continue_running=False,
                error=str(exc),
            )

    def _settle_predictions(
        self,
        db: Session,
    ) -> tuple[int, Optional[str]]:
        try:
            report = self.settlement_runner(db)
            return int(getattr(report, "settled", 0) or 0), None
        except Exception as exc:
            rollback = getattr(db, "rollback", None)
            if callable(rollback):
                rollback()
            return 0, str(exc)

    def close(self) -> None:
        self.browser_session.close()

    def _series_loaded(
        self,
        expected_series_id: int,
    ) -> bool:
        try:
            catalog = self.catalog_service.parse(
                self.browser_session.html()
            )
        except Exception:
            return False

        return catalog.selected_series_id == int(expected_series_id)
