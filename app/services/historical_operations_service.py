from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatch,
    HistoricalCaptureBatchItem,
    HistoricalCaptureBatchService,
)
from app.services.import_pipeline_service import (
    ImportPipeline,
    ImportPipelineService,
)
from app.services.modus_capture_assistant_runtime import (
    capture_assistant_service,
)
from app.services.modus_capture_assistant_service import (
    CaptureAssistantStatus,
)
from app.services.warehouse_dashboard_service import (
    WarehouseDashboard,
    WarehouseDashboardService,
)


@dataclass(frozen=True)
class HistoricalOperations:
    root: Path
    batch: Optional[HistoricalCaptureBatch]
    assistant: CaptureAssistantStatus
    import_pipeline: ImportPipeline
    warehouse: WarehouseDashboard

    @property
    def batch_exists(self) -> bool:
        return self.batch is not None

    @property
    def current_group(
        self,
    ) -> Optional[HistoricalCaptureBatchItem]:
        if self.batch is None:
            return None

        return self.batch.next_item

    @property
    def capture_complete(self) -> bool:
        return (
            self.batch is not None
            and self.batch.total_groups > 0
            and self.batch.remaining_groups == 0
        )

    @property
    def next_action(self) -> str:
        if self.batch is None:
            return "Build a historical capture batch."

        if self.current_group is not None:
            if self.assistant.running:
                return (
                    "Continue capturing "
                    f"{self.current_group.series_label} · "
                    f"{self.current_group.week_label} · "
                    f"{self.current_group.group}."
                )

            return (
                "Start capture for "
                f"{self.current_group.series_label} · "
                f"{self.current_group.week_label} · "
                f"{self.current_group.group}."
            )

        if not self.import_pipeline.queue_exists:
            return "Build the Historical Import Queue."

        if (
            self.import_pipeline.engine_exists
            and self.import_pipeline.engine.remaining_count > 0
        ):
            return "Continue the Historical Import Engine."

        return "Review warehouse and data-quality status."


class HistoricalOperationsService:
    """Read-only orchestration view of the historical data pipeline."""

    def __init__(self) -> None:
        self.batch_service = HistoricalCaptureBatchService()
        self.import_pipeline_service = ImportPipelineService()
        self.warehouse_service = WarehouseDashboardService()

    def build(
        self,
        db: Session,
        *,
        root: str | Path,
    ) -> HistoricalOperations:
        root_path = Path(root).expanduser().resolve()

        batch = None

        try:
            batch = self.batch_service.load(root_path)
        except ValueError:
            batch = None

        import_pipeline = self.import_pipeline_service.build(
            db,
            root_path,
        )

        warehouse = self.warehouse_service.build(
            db,
            capture_root=root_path,
        )

        return HistoricalOperations(
            root=root_path,
            batch=batch,
            assistant=capture_assistant_service.status(),
            import_pipeline=import_pipeline,
            warehouse=warehouse,
        )
