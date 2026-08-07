from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.capture_library_service import (
    CaptureLibraryEntry,
    DEFAULT_CAPTURE_ROOT,
)
from app.services.capture_history_dashboard_service import (
    CaptureHistoryDashboard,
    CaptureHistoryDashboardService,
)
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)
from app.services.current_capture_session_service import (
    CurrentCaptureSessionService,
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
class OperationsDashboard:
    active_capture: Optional[CaptureLibraryEntry]
    assistant: CaptureAssistantStatus
    warehouse: WarehouseDashboard
    import_pipeline: ImportPipeline
    latest_capture_summary: Optional[CaptureIterationSummary]
    capture_history: CaptureHistoryDashboard

    @property
    def capture_running(self) -> bool:
        return self.active_capture is not None

    @property
    def next_match_id(self) -> Optional[int]:
        if self.active_capture is None:
            return None
        return self.active_capture.next_match_id


class OperationsDashboardService:
    """Read-only operational summary built from existing services."""

    def __init__(
        self,
        *,
        workflow_service=None,
    ) -> None:
        self.current_capture_service = CurrentCaptureSessionService()
        self.warehouse_service = WarehouseDashboardService()
        self.import_pipeline_service = ImportPipelineService()
        self.capture_history_service = (
            CaptureHistoryDashboardService()
        )
        self.workflow_service = workflow_service

    def build(
        self,
        db: Session,
        *,
        capture_root: str | Path = DEFAULT_CAPTURE_ROOT,
    ) -> OperationsDashboard:
        active_capture = self.current_capture_service.latest_incomplete(
            capture_root
        )

        warehouse = self.warehouse_service.build(
            db,
            capture_root=capture_root,
        )

        pipeline = self.import_pipeline_service.build(
            db,
            capture_root,
        )

        capture_history = self.capture_history_service.build(
            db,
            capture_root=capture_root,
        )

        return OperationsDashboard(
            active_capture=active_capture,
            assistant=capture_assistant_service.status(),
            warehouse=warehouse,
            import_pipeline=pipeline,
            latest_capture_summary=(
                self.workflow_service.latest_capture_summary()
                if self.workflow_service is not None
                else None
            ),
            capture_history=capture_history,
        )
