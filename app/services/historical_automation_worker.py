from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.historical_automation_service import (
    HistoricalAutomationService,
)


@dataclass(frozen=True)
class HistoricalAutomationWorkerStatus:
    root: str
    running: bool
    started_at: Optional[str]
    updated_at: Optional[str]
    cycles: int
    last_action: Optional[str]
    last_message: str
    last_error: Optional[str]


class HistoricalAutomationWorker:
    """Background loop for historical automation cycles."""

    def __init__(
        self,
        *,
        automation_service: Optional[
            HistoricalAutomationService
        ] = None,
        db_session_factory: Callable[[], Session] = SessionLocal,
        interval_seconds: float = 1.0,
    ) -> None:
        self.automation_service = (
            automation_service
            or HistoricalAutomationService()
        )
        self.db_session_factory = db_session_factory
        self.interval_seconds = interval_seconds

        self._lock = threading.RLock()
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._statuses: Dict[
            str,
            HistoricalAutomationWorkerStatus,
        ] = {}

    def start(
        self,
        root: str | Path,
    ) -> HistoricalAutomationWorkerStatus:
        root_path = str(
            Path(root).expanduser().resolve()
        )

        with self._lock:
            thread = self._threads.get(root_path)

            if thread is not None and thread.is_alive():
                return self.status(root_path)

            stop_event = threading.Event()
            now = self._now()

            self._stop_events[root_path] = stop_event
            self._statuses[root_path] = (
                HistoricalAutomationWorkerStatus(
                    root=root_path,
                    running=True,
                    started_at=now,
                    updated_at=now,
                    cycles=0,
                    last_action=None,
                    last_message=(
                        "Historical automation worker started."
                    ),
                    last_error=None,
                )
            )

            thread = threading.Thread(
                target=self._run,
                args=(root_path, stop_event),
                name=(
                    "dartsedge-historical-automation-"
                    + str(abs(hash(root_path)))
                ),
                daemon=True,
            )

            self._threads[root_path] = thread
            thread.start()

        return self.status(root_path)

    def stop(
        self,
        root: str | Path,
    ) -> HistoricalAutomationWorkerStatus:
        root_path = str(
            Path(root).expanduser().resolve()
        )

        with self._lock:
            stop_event = self._stop_events.get(root_path)

            if stop_event is not None:
                stop_event.set()

            current = self._statuses.get(root_path)

            if current is None:
                current = self._empty_status(root_path)

            self._statuses[root_path] = (
                HistoricalAutomationWorkerStatus(
                    root=root_path,
                    running=False,
                    started_at=current.started_at,
                    updated_at=self._now(),
                    cycles=current.cycles,
                    last_action=current.last_action,
                    last_message=(
                        "Historical automation worker stopped."
                    ),
                    last_error=current.last_error,
                )
            )

        return self.status(root_path)

    def status(
        self,
        root: str | Path,
    ) -> HistoricalAutomationWorkerStatus:
        root_path = str(
            Path(root).expanduser().resolve()
        )

        with self._lock:
            current = self._statuses.get(root_path)

            if current is None:
                return self._empty_status(root_path)

            thread = self._threads.get(root_path)
            running = bool(
                current.running
                and thread is not None
                and thread.is_alive()
            )

            if running == current.running:
                return current

            updated = HistoricalAutomationWorkerStatus(
                root=current.root,
                running=running,
                started_at=current.started_at,
                updated_at=self._now(),
                cycles=current.cycles,
                last_action=current.last_action,
                last_message=current.last_message,
                last_error=current.last_error,
            )

            self._statuses[root_path] = updated
            return updated

    def _run(
        self,
        root: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.wait(self.interval_seconds):
            db = self.db_session_factory()

            try:
                result = self.automation_service.run_cycle(
                    db,
                    root=root,
                )

                with self._lock:
                    current = self._statuses[root]

                    self._statuses[root] = (
                        HistoricalAutomationWorkerStatus(
                            root=root,
                            running=True,
                            started_at=current.started_at,
                            updated_at=self._now(),
                            cycles=current.cycles + 1,
                            last_action=result.action,
                            last_message=result.message,
                            last_error=result.error,
                        )
                    )

                if not result.continue_running:
                    stop_event.set()

            except Exception as exc:
                rollback = getattr(db, "rollback", None)

                if callable(rollback):
                    rollback()

                with self._lock:
                    current = self._statuses[root]

                    self._statuses[root] = (
                        HistoricalAutomationWorkerStatus(
                            root=root,
                            running=False,
                            started_at=current.started_at,
                            updated_at=self._now(),
                            cycles=current.cycles + 1,
                            last_action=current.last_action,
                            last_message=(
                                "Historical automation worker failed."
                            ),
                            last_error=str(exc),
                        )
                    )

                stop_event.set()

            finally:
                db.close()

        with self._lock:
            current = self._statuses.get(
                root,
                self._empty_status(root),
            )

            self._statuses[root] = (
                HistoricalAutomationWorkerStatus(
                    root=root,
                    running=False,
                    started_at=current.started_at,
                    updated_at=self._now(),
                    cycles=current.cycles,
                    last_action=current.last_action,
                    last_message=current.last_message,
                    last_error=current.last_error,
                )
            )

    @staticmethod
    def _empty_status(
        root: str,
    ) -> HistoricalAutomationWorkerStatus:
        return HistoricalAutomationWorkerStatus(
            root=root,
            running=False,
            started_at=None,
            updated_at=None,
            cycles=0,
            last_action=None,
            last_message=(
                "Historical automation worker has not started."
            ),
            last_error=None,
        )

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


historical_automation_worker = HistoricalAutomationWorker()
