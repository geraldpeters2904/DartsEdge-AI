
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Optional

from app.db import SessionLocal
from app.services.live_fixture_edge_capture_service import (
    run_live_fixture_edge_capture,
)


@dataclass(frozen=True)
class LiveEdgeMonitorStatus:
    running: bool
    started_at: Optional[str]
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    runs: int
    failures: int
    last_fixture_count: int
    last_priced_rows: int
    last_value_rows: int
    last_message: str
    last_error: Optional[str]


class LiveEdgeMonitor:
    def __init__(
        self,
        *,
        interval_seconds: float = 300.0,
        initial_delay_seconds: float = 20.0,
    ) -> None:
        self.interval_seconds = max(
            60.0,
            float(interval_seconds),
        )
        self.initial_delay_seconds = max(
            0.0,
            float(initial_delay_seconds),
        )
        self._lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._thread = None
        self._stop_event = threading.Event()
        self._status = LiveEdgeMonitorStatus(
            running=False,
            started_at=None,
            last_run_at=None,
            next_run_at=None,
            runs=0,
            failures=0,
            last_fixture_count=0,
            last_priced_rows=0,
            last_value_rows=0,
            last_message="Live Edge monitor has not started.",
            last_error=None,
        )

    def _copy(self, **changes):
        values = self._status.__dict__.copy()
        values.update(changes)
        self._status = LiveEdgeMonitorStatus(**values)
        return self._status

    def status(self):
        with self._lock:
            alive = bool(
                self._thread is not None
                and self._thread.is_alive()
                and not self._stop_event.is_set()
            )
            if alive != self._status.running:
                self._copy(running=alive)
            return self._status

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
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
                last_message="Live Edge monitor started.",
                last_error=None,
            )

            self._thread = threading.Thread(
                target=self._run,
                name="dartsedge-live-edge-monitor",
                daemon=True,
            )
            self._thread.start()
            return self._status

    def stop(self):
        self._stop_event.set()

        with self._lock:
            return self._copy(
                running=False,
                next_run_at=None,
                last_message="Live Edge monitor stopped.",
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
            report = run_live_fixture_edge_capture(
                db
            )

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
                    last_fixture_count=int(
                        report.future_fixtures
                    ),
                    last_priced_rows=int(
                        report.priced_edge_rows
                    ),
                    last_value_rows=int(
                        report.value_rows
                    ),
                    last_message=report.message,
                    last_error=report.error,
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
                    failures=self._status.failures + 1,
                    last_message="Live Edge monitor cycle failed.",
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


live_edge_monitor = LiveEdgeMonitor()
