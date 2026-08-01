from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class HistoricalCaptureIterationResult:
    advanced: bool
    completed: bool
    message: str
    error: Optional[str] = None


class HistoricalCaptureEngine:
    """
    Executes one capture iteration.

    One iteration means:

    • determine current match
    • capture it
    • write HTML
    • refresh workflow
    • advance to the next match
    """

    def run_iteration(
        self,
        root: str | Path,
    ) -> HistoricalCaptureIterationResult:
        raise NotImplementedError