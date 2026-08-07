from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.modus_fixture_discovery_service import (
    ModusFixtureDiscoveryService,
)


@dataclass(frozen=True)
class ModusFixtureWorkerStatus:
    target: str
    series_id: int
    week_id: int
    group: str
    running: bool
    started_at: Optional[str]
    updated_at: Optional[str]
    checks: int
    imported_cycles: int
    unchanged_cycles: int
    fixtures_seen: int
    last_action: Optional[str]
    last_message: str
    last_error: Optional[str]


class ModusFixtureWorker:
    """Periodically discover and import one MODUS fixture page."""

    def __init__(
        self,
        *,
        discovery_service: Optional[
            ModusFixtureDiscoveryService
        ] = None,
        db_session_factory: Callable[[], Session] = SessionLocal,
        interval_seconds: float = 300.0,
    ) -> None:
        self.discovery_service = (
            discovery_service
            or ModusFixtureDiscoveryService()
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
            ModusFixtureWorkerStatus,
        ] = {}

    def start(
        self,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureWorkerStatus:
        target = self._target(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

        with self._lock:
            thread = self._threads.get(target)

            if thread is not None and thread.is_alive():
                return self.status(
                    series_id=series_id,
                    week_id=week_id,
                    group=group,
                )

            stop_event = threading.Event()
            now = self._now()

            self._stop_events[target] = stop_event
            self._statuses[target] = ModusFixtureWorkerStatus(
                target=target,
                series_id=int(series_id),
                week_id=int(week_id),
                group=str(group).strip(),
                running=True,
                started_at=now,
                updated_at=now,
                checks=0,
                imported_cycles=0,
                unchanged_cycles=0,
                fixtures_seen=0,
                last_action=None,
                last_message="MODUS fixture worker started.",
                last_error=None,
            )

            thread = threading.Thread(
                target=self._run,
                args=(
                    target,
                    int(series_id),
                    int(week_id),
                    str(group).strip(),
                    stop_event,
                ),
                name=(
                    "dartsedge-modus-fixtures-"
                    + str(abs(hash(target)))
                ),
                daemon=True,
            )

            self._threads[target] = thread
            thread.start()

        return self.status(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

    def stop(
        self,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureWorkerStatus:
        target = self._target(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

        with self._lock:
            stop_event = self._stop_events.get(target)

            if stop_event is not None:
                stop_event.set()

            current = self._statuses.get(target)

            if current is None:
                current = self._empty_status(
                    series_id=series_id,
                    week_id=week_id,
                    group=group,
                )

            self._statuses[target] = self._copy_status(
                current,
                running=False,
                updated_at=self._now(),
                last_message="MODUS fixture worker stopped.",
            )

        return self.status(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

    def status(
        self,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureWorkerStatus:
        target = self._target(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

        with self._lock:
            current = self._statuses.get(target)

            if current is None:
                return self._empty_status(
                    series_id=series_id,
                    week_id=week_id,
                    group=group,
                )

            thread = self._threads.get(target)
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
            self._statuses[target] = updated
            return updated

    def _run(
        self,
        target: str,
        series_id: int,
        week_id: int,
        group: str,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.is_set():
            db = self.db_session_factory()

            try:
                result = self.discovery_service.discover(
                    db,
                    series_id=series_id,
                    week_id=week_id,
                    group=group,
                )

                fixture_count = (
                    result.import_result.fixture_count
                    if result.import_result is not None
                    else 0
                )

                with self._lock:
                    current = self._statuses[target]

                    self._statuses[target] = (
                        ModusFixtureWorkerStatus(
                            target=target,
                            series_id=series_id,
                            week_id=week_id,
                            group=group,
                            running=True,
                            started_at=current.started_at,
                            updated_at=self._now(),
                            checks=current.checks + 1,
                            imported_cycles=(
                                current.imported_cycles
                                + (1 if result.imported else 0)
                            ),
                            unchanged_cycles=(
                                current.unchanged_cycles
                                + (1 if result.unchanged else 0)
                            ),
                            fixtures_seen=(
                                current.fixtures_seen
                                + fixture_count
                            ),
                            last_action=result.action,
                            last_message=result.message,
                            last_error=None,
                        )
                    )

            except Exception as exc:
                rollback = getattr(db, "rollback", None)

                if callable(rollback):
                    rollback()

                with self._lock:
                    current = self._statuses[target]

                    self._statuses[target] = self._copy_status(
                        current,
                        running=False,
                        updated_at=self._now(),
                        checks=current.checks + 1,
                        last_message=(
                            "MODUS fixture worker failed."
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
                target,
                self._empty_status(
                    series_id=series_id,
                    week_id=week_id,
                    group=group,
                ),
            )

            self._statuses[target] = self._copy_status(
                current,
                running=False,
                updated_at=self._now(),
            )

    @staticmethod
    def _target(
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> str:
        clean_group = str(group or "").strip()

        if not clean_group:
            raise ValueError("MODUS group must not be blank.")

        return (
            f"series={int(series_id)}|"
            f"week={int(week_id)}|"
            f"group={clean_group.casefold()}"
        )

    @classmethod
    def _empty_status(
        cls,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureWorkerStatus:
        target = cls._target(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

        return ModusFixtureWorkerStatus(
            target=target,
            series_id=int(series_id),
            week_id=int(week_id),
            group=str(group).strip(),
            running=False,
            started_at=None,
            updated_at=None,
            checks=0,
            imported_cycles=0,
            unchanged_cycles=0,
            fixtures_seen=0,
            last_action=None,
            last_message=(
                "MODUS fixture worker has not started."
            ),
            last_error=None,
        )

    @staticmethod
    def _copy_status(
        current: ModusFixtureWorkerStatus,
        **changes,
    ) -> ModusFixtureWorkerStatus:
        values = {
            "target": current.target,
            "series_id": current.series_id,
            "week_id": current.week_id,
            "group": current.group,
            "running": current.running,
            "started_at": current.started_at,
            "updated_at": current.updated_at,
            "checks": current.checks,
            "imported_cycles": current.imported_cycles,
            "unchanged_cycles": current.unchanged_cycles,
            "fixtures_seen": current.fixtures_seen,
            "last_action": current.last_action,
            "last_message": current.last_message,
            "last_error": current.last_error,
        }
        values.update(changes)
        return ModusFixtureWorkerStatus(**values)

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()


modus_fixture_worker = ModusFixtureWorker()
