from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Optional

from app.db import SessionLocal
from app.services.current_match_enrichment_v33_dual_low_history_risk_flag_service import (
    CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService,
)
from app.services.current_match_enrichment_v33_sparse_consensus_risk_diagnostic_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService,
)


@dataclass(frozen=True)
class SparseConsensusRiskMonitorStatus:
    running: bool
    started_at: Optional[str]
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    runs: int
    failures: int
    density: Optional[float]
    risk_state: str
    elevated: bool
    high: bool
    segment_matches: int
    flagged_matches: int
    last_message: str
    last_error: Optional[str]


class SparseConsensusRiskMonitor:
    """
    Refresh sparse-consensus regime diagnostics outside
    interactive HTTP requests.
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 900.0,
        initial_delay_seconds: float = 30.0,
        window_size: int = 1000,
    ) -> None:
        self.interval_seconds = max(
            300.0,
            float(interval_seconds),
        )
        self.initial_delay_seconds = max(
            0.0,
            float(initial_delay_seconds),
        )
        self.window_size = max(
            1,
            int(window_size),
        )

        self._lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._report = None

        self._status = SparseConsensusRiskMonitorStatus(
            running=False,
            started_at=None,
            last_run_at=None,
            next_run_at=None,
            runs=0,
            failures=0,
            density=None,
            risk_state="UNKNOWN",
            elevated=False,
            high=False,
            segment_matches=0,
            flagged_matches=0,
            last_message=(
                "Sparse-consensus risk monitor "
                "has not started."
            ),
            last_error=None,
        )

    def _copy(self, **changes):
        values = self._status.__dict__.copy()
        values.update(changes)

        self._status = (
            SparseConsensusRiskMonitorStatus(
                **values
            )
        )

        return self._status

    def status(self):
        with self._lock:
            alive = bool(
                self._thread is not None
                and self._thread.is_alive()
                and not self._stop_event.is_set()
            )

            if alive != self._status.running:
                self._copy(
                    running=alive
                )

            return self._status

    def latest_report(self):
        with self._lock:
            return self._report

    def start(self):
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return self.status()

            self._stop_event = threading.Event()
            now = datetime.utcnow()

            self._copy(
                running=True,
                started_at=now.isoformat(),
                next_run_at=(
                    now
                    + timedelta(
                        seconds=self.initial_delay_seconds
                    )
                ).isoformat(),
                last_message=(
                    "Sparse-consensus risk monitor started."
                ),
                last_error=None,
            )

            self._thread = threading.Thread(
                target=self._run,
                name=(
                    "dartsedge-sparse-consensus-risk-monitor"
                ),
                daemon=True,
            )

            self._thread.start()

            return self._status

    def stop(self):
        self._stop_event.set()

        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=5.0)

        with self._lock:
            return self._copy(
                running=False,
                next_run_at=None,
                last_message=(
                    "Sparse-consensus risk monitor stopped."
                ),
            )

    def run_once(self):
        if not self._run_lock.acquire(blocking=False):
            return self.status()

        try:
            return self._run_once_locked()
        finally:
            self._run_lock.release()

    def _run_once_locked(self):
        db = SessionLocal()

        try:
            match_ids = (
                CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService
                ._select_match_ids(
                    db,
                    offset=0,
                    limit=1000000,
                )
            )

            total_completed = len(
                match_ids
            )

            offset = max(
                total_completed
                - self.window_size,
                0,
            )

            report = (
                CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService()
                .analyse(
                    db,
                    offset=offset,
                    window_size=self.window_size,
                    probability_lower=65.0,
                    probability_upper=70.0,
                    history_threshold=3,
                    agreement_threshold=100.0,
                    competition_code="MODUS",
                )
            )

            now = datetime.utcnow()

            with self._lock:
                self._report = report

                self._copy(
                    last_run_at=now.isoformat(),
                    next_run_at=(
                        now
                        + timedelta(
                            seconds=self.interval_seconds
                        )
                    ).isoformat()
                    if self._status.running
                    else None,
                    runs=self._status.runs + 1,
                    density=report.density,
                    risk_state=str(
                        report.risk_state
                    ),
                    elevated=bool(
                        report.elevated
                    ),
                    high=bool(
                        report.high
                    ),
                    segment_matches=int(
                        report.segment_matches
                    ),
                    flagged_matches=int(
                        report.flagged_matches
                    ),
                    last_message=(
                        "Sparse-consensus regime "
                        "risk refreshed."
                    ),
                    last_error=None,
                )

        except Exception as exc:
            now = datetime.utcnow()

            with self._lock:
                self._copy(
                    last_run_at=now.isoformat(),
                    next_run_at=(
                        now
                        + timedelta(
                            seconds=self.interval_seconds
                        )
                    ).isoformat()
                    if self._status.running
                    else None,
                    runs=self._status.runs + 1,
                    failures=(
                        self._status.failures + 1
                    ),
                    last_message=(
                        "Sparse-consensus risk "
                        "refresh failed."
                    ),
                    last_error=str(exc),
                )

        finally:
            db.close()

        return self.status()

    def _run(self):
        if self.initial_delay_seconds:
            if self._stop_event.wait(
                self.initial_delay_seconds
            ):
                return

        while not self._stop_event.is_set():
            self.run_once()

            if self._stop_event.wait(
                self.interval_seconds
            ):
                break

        with self._lock:
            self._copy(
                running=False,
                next_run_at=None,
            )


sparse_consensus_risk_monitor = (
    SparseConsensusRiskMonitor()
)
