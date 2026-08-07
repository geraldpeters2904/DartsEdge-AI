from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.capture_iteration_history import (
    CaptureIterationHistory,
)
from app.services.capture_iteration_history_service import (
    CaptureIterationHistoryService,
)


@dataclass(frozen=True)
class CaptureHistoryDashboard:
    capture_root: str
    recent_records: List[CaptureIterationHistory]

    total_iterations: int
    successful_iterations: int
    waiting_iterations: int
    failed_iterations: int

    success_rate_percent: float
    average_duration_seconds: float
    total_bytes_written: int
    average_bytes_written: float
    total_retries: int


class CaptureHistoryDashboardService:
    """Build read-only capture-history metrics for one root."""

    def __init__(self) -> None:
        self.history_service = CaptureIterationHistoryService()

    def build(
        self,
        db: Session,
        *,
        capture_root: str | Path,
        recent_limit: int = 25,
    ) -> CaptureHistoryDashboard:
        root = str(Path(capture_root).expanduser())

        base_query = db.query(
            CaptureIterationHistory
        ).filter(
            CaptureIterationHistory.capture_root == root
        )

        total_iterations = base_query.count()

        successful_iterations = (
            base_query.filter(
                CaptureIterationHistory.matches_captured > 0,
                CaptureIterationHistory.errors == 0,
            )
            .count()
        )

        waiting_iterations = (
            base_query.filter(
                CaptureIterationHistory.captures_waiting > 0,
                CaptureIterationHistory.errors == 0,
            )
            .count()
        )

        failed_iterations = (
            base_query.filter(
                CaptureIterationHistory.errors > 0
            )
            .count()
        )

        aggregates = (
            db.query(
                func.avg(
                    CaptureIterationHistory.duration_seconds
                ),
                func.sum(
                    CaptureIterationHistory.bytes_written
                ),
                func.avg(
                    CaptureIterationHistory.bytes_written
                ),
                func.sum(
                    CaptureIterationHistory.retries_attempted
                ),
            )
            .filter(
                CaptureIterationHistory.capture_root == root
            )
            .one()
        )

        average_duration = float(
            aggregates[0] or 0.0
        )
        total_bytes = int(aggregates[1] or 0)
        average_bytes = float(
            aggregates[2] or 0.0
        )
        total_retries = int(aggregates[3] or 0)

        success_rate = (
            successful_iterations / total_iterations * 100
            if total_iterations
            else 0.0
        )

        return CaptureHistoryDashboard(
            capture_root=root,
            recent_records=self.history_service.recent(
                db,
                capture_root=root,
                limit=recent_limit,
            ),
            total_iterations=total_iterations,
            successful_iterations=successful_iterations,
            waiting_iterations=waiting_iterations,
            failed_iterations=failed_iterations,
            success_rate_percent=round(success_rate, 1),
            average_duration_seconds=round(
                average_duration,
                2,
            ),
            total_bytes_written=total_bytes,
            average_bytes_written=round(
                average_bytes,
                1,
            ),
            total_retries=total_retries,
        )
