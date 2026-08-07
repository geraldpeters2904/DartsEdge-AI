from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import sleep
from typing import Callable, Optional


@dataclass(frozen=True)
class SyncJobResult:
    name: str
    ran: bool
    success: bool
    message: str
    error: Optional[str] = None


@dataclass(frozen=True)
class UnifiedSyncStatus:
    running: bool
    cycles: int
    successful_cycles: int
    failed_cycles: int
    last_started_at: Optional[datetime]
    last_finished_at: Optional[datetime]
    last_message: str
    last_error: Optional[str]
    last_results: tuple[SyncJobResult, ...]


class UnifiedSynchronisationManager:
    """
    Coordinates live and background DartsEdge data jobs.

    Priority order per cycle:
    1. current-series lifecycle sync
    2. result settlement / reconciliation
    3. bookmaker capture
    4. historical backfill

    Each job is optional and isolated. A failed low-priority job does not
    prevent higher-priority jobs in the same cycle from running.
    """

    def __init__(
        self,
        *,
        current_series_sync: Optional[
            Callable[[], object]
        ] = None,
        settlement_sync: Optional[
            Callable[[], object]
        ] = None,
        bookmaker_capture: Optional[
            Callable[[], object]
        ] = None,
        historical_backfill: Optional[
            Callable[[], object]
        ] = None,
        poll_seconds: float = 180.0,
        historical_every_n_cycles: int = 5,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.current_series_sync = current_series_sync
        self.settlement_sync = settlement_sync
        self.bookmaker_capture = bookmaker_capture
        self.historical_backfill = historical_backfill
        self.poll_seconds = max(
            1.0,
            float(
                poll_seconds
            ),
        )
        self.historical_every_n_cycles = max(
            1,
            int(
                historical_every_n_cycles
            ),
        )
        self.sleeper = sleeper

        self._running = False
        self._stop_requested = False
        self._cycles = 0
        self._successful_cycles = 0
        self._failed_cycles = 0
        self._last_started_at = None
        self._last_finished_at = None
        self._last_message = (
            "Unified synchronisation manager has not started."
        )
        self._last_error = None
        self._last_results: tuple[
            SyncJobResult,
            ...,
        ] = ()

    def request_stop(
        self,
    ) -> None:
        self._stop_requested = True
        self._last_message = (
            "Stop requested."
        )

    def status(
        self,
    ) -> UnifiedSyncStatus:
        return UnifiedSyncStatus(
            running=self._running,
            cycles=self._cycles,
            successful_cycles=(
                self._successful_cycles
            ),
            failed_cycles=(
                self._failed_cycles
            ),
            last_started_at=(
                self._last_started_at
            ),
            last_finished_at=(
                self._last_finished_at
            ),
            last_message=(
                self._last_message
            ),
            last_error=(
                self._last_error
            ),
            last_results=(
                self._last_results
            ),
        )

    def _run_job(
        self,
        *,
        name: str,
        callback: Optional[
            Callable[[], object]
        ],
        should_run: bool = True,
    ) -> SyncJobResult:
        if not should_run:
            return SyncJobResult(
                name=name,
                ran=False,
                success=True,
                message="Skipped this cycle.",
            )

        if callback is None:
            return SyncJobResult(
                name=name,
                ran=False,
                success=True,
                message="Job not configured.",
            )

        try:
            result = callback()

            message = (
                getattr(
                    result,
                    "message",
                    None,
                )
                or str(
                    result
                )
                or "Completed."
            )

            return SyncJobResult(
                name=name,
                ran=True,
                success=True,
                message=message,
            )

        except Exception as exc:
            return SyncJobResult(
                name=name,
                ran=True,
                success=False,
                message=(
                    f"{name} failed."
                ),
                error=str(
                    exc
                ),
            )

    def run_cycle(
        self,
    ) -> UnifiedSyncStatus:
        self._cycles += 1
        self._last_started_at = (
            datetime.utcnow()
        )
        self._last_error = None

        results = []

        results.append(
            self._run_job(
                name=(
                    "current-series"
                ),
                callback=(
                    self.current_series_sync
                ),
            )
        )

        results.append(
            self._run_job(
                name=(
                    "settlement"
                ),
                callback=(
                    self.settlement_sync
                ),
            )
        )

        results.append(
            self._run_job(
                name=(
                    "bookmaker-capture"
                ),
                callback=(
                    self.bookmaker_capture
                ),
            )
        )

        historical_due = (
            self._cycles
            % self.historical_every_n_cycles
            == 0
        )

        results.append(
            self._run_job(
                name=(
                    "historical-backfill"
                ),
                callback=(
                    self.historical_backfill
                ),
                should_run=(
                    historical_due
                ),
            )
        )

        failures = [
            item
            for item
            in results
            if (
                item.ran
                and not item.success
            )
        ]

        self._last_results = tuple(
            results
        )

        self._last_finished_at = (
            datetime.utcnow()
        )

        if failures:
            self._failed_cycles += 1
            self._last_error = (
                "; ".join(
                    item.error
                    or item.message
                    for item
                    in failures
                )
            )
            self._last_message = (
                "Unified sync cycle completed with errors."
            )
        else:
            self._successful_cycles += 1
            self._last_message = (
                "Unified sync cycle completed."
            )

        return self.status()

    def run_forever(
        self,
        *,
        max_cycles: Optional[
            int
        ] = None,
    ) -> UnifiedSyncStatus:
        if self._running:
            raise RuntimeError(
                "Unified synchronisation manager is already running."
            )

        self._running = True
        self._stop_requested = False

        try:
            while not self._stop_requested:
                if (
                    max_cycles is not None
                    and self._cycles
                    >= int(
                        max_cycles
                    )
                ):
                    break

                self.run_cycle()

                if not self._stop_requested:
                    self.sleeper(
                        self.poll_seconds
                    )

        finally:
            self._running = False

        return self.status()
