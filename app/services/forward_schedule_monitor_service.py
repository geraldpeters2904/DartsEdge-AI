from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
from typing import Optional

from app.services.forward_schedule_discovery_service import (
    run_forward_schedule_discovery,
)
from app.services.automatic_odds_capture_trigger_service import (
    automatic_odds_capture_trigger,
)


@dataclass(frozen=True)
class ForwardScheduleMonitorStatus:
    running: bool
    started_at: Optional[str]
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    runs: int
    failures: int
    latest_series: Optional[str]
    latest_week: Optional[str]
    future_fixtures: int
    odds_capture_triggered: bool
    odds_capture_ready: bool
    odds_capture_at: Optional[str]
    odds_prices_extracted: int
    odds_prices_stored: int
    odds_capture_message: Optional[str]
    odds_capture_error: Optional[str]
    last_message: str
    last_error: Optional[str]
    discovery_targets: tuple = ()


class ForwardScheduleMonitor:
    def __init__(
        self,
        *,
        interval_seconds: float = 900.0,
        initial_delay_seconds: float = 10.0,
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
        self._thread = None
        self._stop_event = threading.Event()
        self._status = ForwardScheduleMonitorStatus(
            running=False,
            started_at=None,
            last_run_at=None,
            next_run_at=None,
            runs=0,
            failures=0,
            latest_series=None,
            latest_week=None,
            future_fixtures=0,
            odds_capture_triggered=False,
            odds_capture_ready=True,
            odds_capture_at=None,
            odds_prices_extracted=0,
            odds_prices_stored=0,
            odds_capture_message=None,
            odds_capture_error=None,
            last_message=(
                "Forward schedule monitor has not started."
            ),
            last_error=None,
            discovery_targets=(),
        )

    def _copy(self, **changes):
        values = self._status.__dict__.copy()
        values.update(changes)
        self._status = ForwardScheduleMonitorStatus(
            **values
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
                        seconds=(
                            self.initial_delay_seconds
                        )
                    )
                ).isoformat(),
                last_message=(
                    "Forward schedule monitor started."
                ),
                last_error=None,
            )

            self._thread = threading.Thread(
                target=self._run,
                name=(
                    "dartsedge-forward-schedule-monitor"
                ),
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
                last_message=(
                    "Forward schedule monitor stopped."
                ),
            )

    def run_once(self):
        try:
            report = (
                run_forward_schedule_discovery()
            )

            odds_capture = (
                automatic_odds_capture_trigger.consider(
                    future_fixtures=int(
                        report.future_fixtures
                    )
                )
            )

            now = datetime.utcnow()

            with self._lock:
                self._copy(
                    last_run_at=now.isoformat(),
                    next_run_at=(
                        now
                        + timedelta(
                            seconds=(
                                self.interval_seconds
                            )
                        )
                    ).isoformat()
                    if self._status.running
                    else None,
                    runs=(
                        self._status.runs
                        + 1
                    ),
                    latest_series=(
                        report.series_label
                    ),
                    latest_week=(
                        report.week_label
                    ),
                    future_fixtures=int(
                        report.future_fixtures
                    ),
                    odds_capture_triggered=(
                        odds_capture.triggered
                    ),
                    odds_capture_ready=(
                        odds_capture.ready
                    ),
                    odds_capture_at=(
                        odds_capture.captured_at
                    ),
                    odds_prices_extracted=(
                        odds_capture.extracted_prices
                    ),
                    odds_prices_stored=(
                        odds_capture.stored_prices
                    ),
                    odds_capture_message=(
                        odds_capture.message
                    ),
                    odds_capture_error=(
                        odds_capture.error
                    ),
                    discovery_targets=tuple(
                        getattr(
                            report,
                            "target_results",
                            (),
                        )
                    ),
                    last_message=(
                        report.message
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
                            seconds=(
                                self.interval_seconds
                            )
                        )
                    ).isoformat()
                    if self._status.running
                    else None,
                    runs=(
                        self._status.runs
                        + 1
                    ),
                    failures=(
                        self._status.failures
                        + 1
                    ),
                    last_message=(
                        "Forward schedule discovery failed."
                    ),
                    last_error=str(
                        exc
                    ),
                )

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


forward_schedule_monitor = ForwardScheduleMonitor()
