from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import threading
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.player_career_profile_cache_service import (
    PlayerCareerProfileCacheService,
)
from app.services.warehouse_manager_service import (
    WarehouseManagerResult,
    WarehouseManagerService,
)


@dataclass(frozen=True)
class WarehouseManagerRunnerStatus:
    root: str
    running: bool
    started_at: Optional[str]
    updated_at: Optional[str]
    cycles: int
    prepared_cycles: int
    captured_cycles: int
    imported_cycles: int
    completed_series: int
    remaining_series: int
    current_series: Optional[str]
    last_action: Optional[str]
    last_message: str
    last_error: Optional[str]


class WarehouseManagerRunner:
    """Continuously execute warehouse-manager cycles until completion."""

    def __init__(
        self,
        *,
        manager_service: Optional[
            WarehouseManagerService
        ] = None,
        profile_cache_service: Optional[
            PlayerCareerProfileCacheService
        ] = None,
        db_session_factory: Callable[[], Session] = SessionLocal,
        interval_seconds: float = 0.25,
    ) -> None:
        self.manager_service = (
            manager_service or WarehouseManagerService()
        )
        self.profile_cache_service = (
            profile_cache_service
            or PlayerCareerProfileCacheService()
        )
        self.db_session_factory = db_session_factory
        self.interval_seconds = max(
            float(interval_seconds),
            0.01,
        )

        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status: Optional[
            WarehouseManagerRunnerStatus
        ] = None

    def start(
        self,
        *,
        root: str | Path,
        master_catalog_html: str,
        watch_folder: str = "~/Downloads",
    ) -> WarehouseManagerRunnerStatus:
        root_path = str(
            Path(root).expanduser().resolve()
        )

        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
            ):
                return self.status()

            now = self._now()
            self._stop_event = threading.Event()
            self._status = WarehouseManagerRunnerStatus(
                root=root_path,
                running=True,
                started_at=now,
                updated_at=now,
                cycles=0,
                prepared_cycles=0,
                captured_cycles=0,
                imported_cycles=0,
                completed_series=0,
                remaining_series=0,
                current_series=None,
                last_action=None,
                last_message="Warehouse Manager Runner started.",
                last_error=None,
            )

            self._thread = threading.Thread(
                target=self._run,
                args=(
                    root_path,
                    master_catalog_html,
                    watch_folder,
                ),
                name="dartsedge-warehouse-manager-runner",
                daemon=True,
            )
            self._thread.start()

        return self.status()

    def stop(self) -> WarehouseManagerRunnerStatus:
        with self._lock:
            self._stop_event.set()

            if self._status is None:
                self._status = self._empty_status()

            self._status = self._copy_status(
                self._status,
                running=False,
                updated_at=self._now(),
                last_message="Warehouse Manager Runner stopped.",
            )

        return self.status()

    def status(self) -> WarehouseManagerRunnerStatus:
        with self._lock:
            if self._status is None:
                return self._empty_status()

            running = bool(
                self._status.running
                and self._thread is not None
                and self._thread.is_alive()
            )

            if running == self._status.running:
                return self._status

            self._status = self._copy_status(
                self._status,
                running=running,
                updated_at=self._now(),
            )
            return self._status

    def run_foreground(
        self,
        *,
        root: str | Path,
        master_catalog_html: str,
        watch_folder: str = "~/Downloads",
        progress_callback=None,
    ) -> WarehouseManagerRunnerStatus:
        root_path = str(
            Path(root).expanduser().resolve()
        )

        now = self._now()
        self._status = WarehouseManagerRunnerStatus(
            root=root_path,
            running=True,
            started_at=now,
            updated_at=now,
            cycles=0,
            prepared_cycles=0,
            captured_cycles=0,
            imported_cycles=0,
            completed_series=0,
            remaining_series=0,
            current_series=None,
            last_action=None,
            last_message="Warehouse Manager Runner started.",
            last_error=None,
        )
        self._stop_event = threading.Event()

        self._run(
            root_path,
            master_catalog_html,
            watch_folder,
            progress_callback=progress_callback,
        )

        return self.status()

    def _run(
        self,
        root: str,
        master_catalog_html: str,
        watch_folder: str,
        progress_callback=None,
    ) -> None:
        try:
            while not self._stop_event.is_set():
                db = self.db_session_factory()

                try:
                    result = self.manager_service.run_cycle(
                        db,
                        root=root,
                        master_catalog_html=master_catalog_html,
                        watch_folder=watch_folder,
                    )

                    if result.action == "imported":
                        self._refresh_profiles(db)

                    self._record_result(result)

                    if progress_callback is not None:
                        progress_callback(self.status())

                    if not result.continue_running:
                        self._stop_event.set()

                except Exception as exc:
                    rollback = getattr(db, "rollback", None)

                    if callable(rollback):
                        rollback()

                    with self._lock:
                        current = (
                            self._status
                            or self._empty_status(root)
                        )
                        self._status = self._copy_status(
                            current,
                            running=False,
                            updated_at=self._now(),
                            cycles=current.cycles + 1,
                            last_action="error",
                            last_message=(
                                "Warehouse Manager Runner failed."
                            ),
                            last_error=str(exc),
                        )

                    self._stop_event.set()

                finally:
                    db.close()

                if self._stop_event.wait(
                    self.interval_seconds
                ):
                    break

        finally:
            self.manager_service.close()

            with self._lock:
                current = (
                    self._status
                    or self._empty_status(root)
                )
                self._status = self._copy_status(
                    current,
                    running=False,
                    updated_at=self._now(),
                )

    def _refresh_profiles(self, db: Session) -> None:
        player_ids = [
            row[0]
            for row in (
                db.query(
                    PlayerMatchPerformance.player_id
                )
                .distinct()
                .all()
            )
        ]

        if player_ids:
            self.profile_cache_service.refresh_players(
                db,
                player_ids=player_ids,
            )

    def _record_result(
        self,
        result: WarehouseManagerResult,
    ) -> None:
        plan = result.archive_plan
        current_series = (
            result.current_series.series_label
            if result.current_series is not None
            else None
        )

        with self._lock:
            current = self._status or self._empty_status(
                str(result.root)
            )

            self._status = self._copy_status(
                current,
                running=result.continue_running,
                updated_at=self._now(),
                cycles=current.cycles + 1,
                prepared_cycles=(
                    current.prepared_cycles
                    + (1 if result.action == "prepared" else 0)
                ),
                captured_cycles=(
                    current.captured_cycles
                    + (1 if result.action == "captured" else 0)
                ),
                imported_cycles=(
                    current.imported_cycles
                    + (1 if result.action == "imported" else 0)
                ),
                completed_series=(
                    plan.complete_series
                    if plan is not None
                    else current.completed_series
                ),
                remaining_series=(
                    plan.remaining_series
                    if plan is not None
                    else current.remaining_series
                ),
                current_series=current_series,
                last_action=result.action,
                last_message=result.message,
                last_error=result.error,
            )

    @staticmethod
    def _empty_status(
        root: str = "",
    ) -> WarehouseManagerRunnerStatus:
        return WarehouseManagerRunnerStatus(
            root=root,
            running=False,
            started_at=None,
            updated_at=None,
            cycles=0,
            prepared_cycles=0,
            captured_cycles=0,
            imported_cycles=0,
            completed_series=0,
            remaining_series=0,
            current_series=None,
            last_action=None,
            last_message=(
                "Warehouse Manager Runner has not started."
            ),
            last_error=None,
        )

    @staticmethod
    def _copy_status(
        current: WarehouseManagerRunnerStatus,
        **changes,
    ) -> WarehouseManagerRunnerStatus:
        values = {
            "root": current.root,
            "running": current.running,
            "started_at": current.started_at,
            "updated_at": current.updated_at,
            "cycles": current.cycles,
            "prepared_cycles": current.prepared_cycles,
            "captured_cycles": current.captured_cycles,
            "imported_cycles": current.imported_cycles,
            "completed_series": current.completed_series,
            "remaining_series": current.remaining_series,
            "current_series": current.current_series,
            "last_action": current.last_action,
            "last_message": current.last_message,
            "last_error": current.last_error,
        }
        values.update(changes)
        return WarehouseManagerRunnerStatus(**values)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


warehouse_manager_runner = WarehouseManagerRunner()
