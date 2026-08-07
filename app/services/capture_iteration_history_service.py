from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.capture_iteration_history import (
    CaptureIterationHistory,
)
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)


class CaptureIterationHistoryService:
    """Persist and read completed capture iteration summaries."""

    def record(
        self,
        db: Session,
        *,
        capture_root: str | Path,
        provider: str,
        match_id: Optional[int],
        summary: CaptureIterationSummary,
        error_detail: Optional[str] = None,
    ) -> CaptureIterationHistory:
        provider_name = str(provider or "").strip().casefold()

        if not provider_name:
            raise ValueError(
                "Capture history provider is required."
            )

        root = str(Path(capture_root).expanduser())

        record = CaptureIterationHistory(
            capture_root=root,
            provider=provider_name,
            match_id=match_id,
            status=summary.status,
            started_at=summary.started_at,
            finished_at=summary.finished_at,
            duration_seconds=summary.duration_seconds,
            matches_captured=summary.matches_captured,
            bytes_written=summary.bytes_written,
            captures_waiting=summary.captures_waiting,
            retries_attempted=summary.retries_attempted,
            warnings=summary.warnings,
            errors=summary.errors,
            error_detail=error_detail,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def recent(
        self,
        db: Session,
        *,
        capture_root: str | Path,
        limit: int = 25,
    ) -> List[CaptureIterationHistory]:
        safe_limit = max(1, min(int(limit), 250))
        root = str(Path(capture_root).expanduser())

        return (
            db.query(CaptureIterationHistory)
            .filter(
                CaptureIterationHistory.capture_root == root
            )
            .order_by(
                CaptureIterationHistory.started_at.desc(),
                CaptureIterationHistory.id.desc(),
            )
            .limit(safe_limit)
            .all()
        )
