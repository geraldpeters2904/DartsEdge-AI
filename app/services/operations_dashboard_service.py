from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.capture_library_service import (
    CaptureLibraryEntry,
    DEFAULT_CAPTURE_ROOT,
)
from app.services.current_capture_session_service import (
    CurrentCaptureSessionService,
)
from app.services.warehouse_dashboard_service import (
    WarehouseDashboard,
    WarehouseDashboardService,
)


@dataclass(frozen=True)
class OperationsDashboard:
    active_capture: Optional[CaptureLibraryEntry]
    warehouse: WarehouseDashboard

    @property
    def capture_running(self) -> bool:
        return self.active_capture is not None

    @property
    def next_match_id(self) -> Optional[int]:
        if self.active_capture is None:
            return None
        return self.active_capture.next_match_id


class OperationsDashboardService:
    """Read-only operational summary built from existing DartsEdge services."""

    def __init__(self) -> None:
        self.current_capture_service = CurrentCaptureSessionService()
        self.warehouse_service = WarehouseDashboardService()

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

        return OperationsDashboard(
            active_capture=active_capture,
            warehouse=warehouse,
        )
