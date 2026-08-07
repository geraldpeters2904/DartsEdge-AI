from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.automatic_modus_folder_import_service import (
    AutomaticModusFolderImportService,
)
from app.services.warehouse_population_service import (
    WarehousePopulationPlan,
    WarehousePopulationService,
)


@dataclass(frozen=True)
class WarehousePopulationWorkerStatus:
    root: str
    running: bool
    started_at: Optional[str]
    updated_at: Optional[str]
    cycles: int
    imported_folders: int
    imported_matches: int
    queued_folders: int
    remaining_matches: int
    coverage_percent: float
    current_folder: Optional[str]
    last_action: Optional[str]
    last_message: str
    last_error: Optional[str]


class WarehousePopulationWorker:
    """Background worker that executes a warehouse population plan."""

    def __init__(
        self,
        *,
        population_service: Optional[
            WarehousePopulationService
        ] = None,
        folder_import_service: Optional[
            AutomaticModusFolderImportService
        ] = None,
        db_session_factory: Callable[[], Session] = SessionLocal,
        interval_seconds: float = 1.0,
    ) -> None:
        self.population_service = (
            population_service
            or WarehousePopulationService()
        )
        self.folder_import_service = (
            folder_import_service
            or AutomaticModusFolderImportService()
        )
        self.db_session_factory = db_session_factory
        self.interval_seconds = max(
            float(interval_seconds),
            0.01,
        )

        self._lock = threading.RLock()
        self._threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._statuses: Dict[
            str,
            WarehousePopulationWorkerStatus,
        ] = {}

    def start(
        self,
        root: str | Path,
    ) -> WarehousePopulationWorkerStatus:
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
                WarehousePopulationWorkerStatus(
                    root=root_path,
                    running=True,
                    started_at=now,
                    updated_at=now,
                    cycles=0,
                    imported_folders=0,
                    imported_matches=0,
                    queued_folders=0,
                    remaining_matches=0,
                    coverage_percent=0.0,
                    current_folder=None,
                    last_action=None,
                    last_message=(
                        "Warehouse population worker started."
                    ),
                    last_error=None,
                )
            )

            thread = threading.Thread(
                target=self._run,
                args=(root_path, stop_event),
                name=(
                    "dartsedge-warehouse-population-"
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
    ) -> WarehousePopulationWorkerStatus:
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

            self._statuses[root_path] = self._copy_status(
                current,
                running=False,
                updated_at=self._now(),
                last_message=(
                    "Warehouse population worker stopped."
                ),
            )

        return self.status(root_path)

    def status(
        self,
        root: str | Path,
    ) -> WarehousePopulationWorkerStatus:
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

            updated = self._copy_status(
                current,
                running=running,
                updated_at=self._now(),
            )
            self._statuses[root_path] = updated
            return updated

    def _run(
        self,
        root: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            db = self.db_session_factory()

            try:
                plan = self.population_service.build_plan(
                    db,
                    root=root,
                )

                if plan.blocked:
                    self._record_plan(
                        root,
                        plan,
                        action="blocked",
                        message=(
                            "Warehouse population is blocked by "
                            "incomplete or invalid folders."
                        ),
                        error="; ".join(
                            plan.blocking_issues
                        ),
                        running=False,
                    )
                    stop_event.set()
                    continue

                if plan.complete:
                    self._record_plan(
                        root,
                        plan,
                        action="complete",
                        message=(
                            "Warehouse population is complete."
                        ),
                        error=None,
                        running=False,
                    )
                    stop_event.set()
                    continue

                next_item = plan.next_item

                if next_item is None:
                    raise ValueError(
                        "Population plan has no next queue item."
                    )

                self._record_plan(
                    root,
                    plan,
                    action="importing",
                    message=(
                        f"Importing {next_item.series_label} · "
                        f"{next_item.week_label} · "
                        f"{next_item.group}."
                    ),
                    error=None,
                    running=True,
                    current_folder=str(next_item.folder),
                )

                result = self.folder_import_service.import_folder(
                    db,
                    folder=next_item.folder,
                )

                refreshed = self.population_service.build_plan(
                    db,
                    root=root,
                )

                with self._lock:
                    current = self._statuses[root]

                    self._statuses[root] = self._copy_status(
                        current,
                        running=True,
                        updated_at=self._now(),
                        cycles=current.cycles + 1,
                        imported_folders=(
                            current.imported_folders + 1
                        ),
                        imported_matches=(
                            current.imported_matches
                            + result.created_matches
                        ),
                        queued_folders=(
                            refreshed.queued_folders
                        ),
                        remaining_matches=(
                            refreshed.remaining_matches
                        ),
                        coverage_percent=(
                            refreshed.coverage_percent
                        ),
                        current_folder=None,
                        last_action="imported",
                        last_message=(
                            f"Imported {next_item.series_label} · "
                            f"{next_item.week_label} · "
                            f"{next_item.group}. "
                            f"{refreshed.queued_folders} folder(s) "
                            "remain queued."
                        ),
                        last_error=None,
                    )

            except Exception as exc:
                rollback = getattr(db, "rollback", None)

                if callable(rollback):
                    rollback()

                with self._lock:
                    current = self._statuses[root]

                    self._statuses[root] = self._copy_status(
                        current,
                        running=False,
                        updated_at=self._now(),
                        cycles=current.cycles + 1,
                        last_action="error",
                        last_message=(
                            "Warehouse population worker failed."
                        ),
                        last_error=str(exc),
                    )

                stop_event.set()

            finally:
                db.close()

            if stop_event.wait(self.interval_seconds):
                break

        with self._lock:
            current = self._statuses.get(
                root,
                self._empty_status(root),
            )

            self._statuses[root] = self._copy_status(
                current,
                running=False,
                updated_at=self._now(),
            )

    def _record_plan(
        self,
        root: str,
        plan: WarehousePopulationPlan,
        *,
        action: str,
        message: str,
        error: Optional[str],
        running: bool,
        current_folder: Optional[str] = None,
    ) -> None:
        with self._lock:
            current = self._statuses[root]

            self._statuses[root] = self._copy_status(
                current,
                running=running,
                updated_at=self._now(),
                queued_folders=plan.queued_folders,
                remaining_matches=plan.remaining_matches,
                coverage_percent=plan.coverage_percent,
                current_folder=current_folder,
                last_action=action,
                last_message=message,
                last_error=error,
            )

    @staticmethod
    def _empty_status(
        root: str,
    ) -> WarehousePopulationWorkerStatus:
        return WarehousePopulationWorkerStatus(
            root=root,
            running=False,
            started_at=None,
            updated_at=None,
            cycles=0,
            imported_folders=0,
            imported_matches=0,
            queued_folders=0,
            remaining_matches=0,
            coverage_percent=0.0,
            current_folder=None,
            last_action=None,
            last_message=(
                "Warehouse population worker has not started."
            ),
            last_error=None,
        )

    @staticmethod
    def _copy_status(
        current: WarehousePopulationWorkerStatus,
        **changes,
    ) -> WarehousePopulationWorkerStatus:
        values = {
            "root": current.root,
            "running": current.running,
            "started_at": current.started_at,
            "updated_at": current.updated_at,
            "cycles": current.cycles,
            "imported_folders": current.imported_folders,
            "imported_matches": current.imported_matches,
            "queued_folders": current.queued_folders,
            "remaining_matches": current.remaining_matches,
            "coverage_percent": current.coverage_percent,
            "current_folder": current.current_folder,
            "last_action": current.last_action,
            "last_message": current.last_message,
            "last_error": current.last_error,
        }
        values.update(changes)
        return WarehousePopulationWorkerStatus(**values)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


warehouse_population_worker = WarehousePopulationWorker()
