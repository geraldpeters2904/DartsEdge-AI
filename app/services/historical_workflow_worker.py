from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
from typing import Dict, Optional

from app.services.historical_workflow_service import (
    HistoricalWorkflowService,
)


@dataclass(frozen=True)
class HistoricalWorkflowWorkerStatus:
    root: str
    running: bool
    started_at: Optional[str]
    updated_at: Optional[str]
    iterations: int
    last_message: str
    last_error: Optional[str]


class HistoricalWorkflowWorker:
    """Background synchronisation loop for historical capture workflows."""

    def __init__(
        self,
        *,
        workflow_service: Optional[
            HistoricalWorkflowService
        ] = None,
        interval_seconds: float = 1.0,
    ) -> None:
        self.workflow_service = (
            workflow_service or HistoricalWorkflowService()
        )
        self.interval_seconds = interval_seconds

        self._lock = threading.RLock()
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._statuses: Dict[
            str,
            HistoricalWorkflowWorkerStatus,
        ] = {}

    def start(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowWorkerStatus:
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
                HistoricalWorkflowWorkerStatus(
                    root=root_path,
                    running=True,
                    started_at=now,
                    updated_at=now,
                    iterations=0,
                    last_message=(
                        "Historical workflow worker started."
                    ),
                    last_error=None,
                )
            )

            thread = threading.Thread(
                target=self._run,
                args=(root_path, stop_event),
                name=(
                    "dartsedge-historical-workflow-"
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
    ) -> HistoricalWorkflowWorkerStatus:
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
                HistoricalWorkflowWorkerStatus(
                    root=root_path,
                    running=False,
                    started_at=current.started_at,
                    updated_at=self._now(),
                    iterations=current.iterations,
                    last_message=(
                        "Historical workflow worker stopped."
                    ),
                    last_error=current.last_error,
                )
            )

        return self.status(root_path)

    def status(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowWorkerStatus:
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

            updated = HistoricalWorkflowWorkerStatus(
                root=current.root,
                running=running,
                started_at=current.started_at,
                updated_at=self._now(),
                iterations=current.iterations,
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
            try:
                workflow = self.workflow_service.capture_iteration(
                    root
                )

                with self._lock:
                    current = self._statuses[root]
                    message = (
                        "Workflow synchronised. "
                        f"Runner status: {workflow.runner.status}."
                    )

                    self._statuses[root] = (
                        HistoricalWorkflowWorkerStatus(
                            root=root,
                            running=True,
                            started_at=current.started_at,
                            updated_at=self._now(),
                            iterations=current.iterations + 1,
                            last_message=message,
                            last_error=None,
                        )
                    )

                if workflow.runner.status in {
                    "stopped",
                    "completed",
                    "failed",
                }:
                    stop_event.set()

            except Exception as exc:
                with self._lock:
                    current = self._statuses[root]

                    self._statuses[root] = (
                        HistoricalWorkflowWorkerStatus(
                            root=root,
                            running=False,
                            started_at=current.started_at,
                            updated_at=self._now(),
                            iterations=current.iterations + 1,
                            last_message=(
                                "Historical workflow worker failed."
                            ),
                            last_error=str(exc),
                        )
                    )

                stop_event.set()

        with self._lock:
            current = self._statuses.get(
                root,
                self._empty_status(root),
            )

            self._statuses[root] = (
                HistoricalWorkflowWorkerStatus(
                    root=root,
                    running=False,
                    started_at=current.started_at,
                    updated_at=self._now(),
                    iterations=current.iterations,
                    last_message=current.last_message,
                    last_error=current.last_error,
                )
            )

    @staticmethod
    def _empty_status(
        root: str,
    ) -> HistoricalWorkflowWorkerStatus:
        return HistoricalWorkflowWorkerStatus(
            root=root,
            running=False,
            started_at=None,
            updated_at=None,
            iterations=0,
            last_message=(
                "Historical workflow worker has not started."
            ),
            last_error=None,
        )

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


historical_workflow_worker = HistoricalWorkflowWorker()
