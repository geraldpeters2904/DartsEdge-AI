from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class CaptureIterationSummary:
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str = "running"

    matches_captured: int = 0
    players_discovered: int = 0
    statistics_written: int = 0
    odds_captured: int = 0
    bytes_written: int = 0
    captures_waiting: int = 0
    retries_attempted: int = 0

    warnings: int = 0
    errors: int = 0

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.finished_at is None:
            return None

        return (
            self.finished_at - self.started_at
        ).total_seconds()
