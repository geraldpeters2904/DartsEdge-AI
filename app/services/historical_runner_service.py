from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Optional

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchItem,
    HistoricalCaptureBatchService,
)


RUNNER_FILENAME = ".historical_runner.json"

RUNNER_STATUSES = {
    "stopped",
    "running",
    "paused",
    "completed",
    "failed",
}


@dataclass(frozen=True)
class HistoricalRunnerState:
    root: Path
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str]
    paused_at: Optional[str]
    stopped_at: Optional[str]
    completed_at: Optional[str]

    current_position: Optional[int]
    current_series_id: Optional[int]
    current_series_label: Optional[str]
    current_week_id: Optional[int]
    current_week_label: Optional[str]
    current_group: Optional[str]
    current_match_id: Optional[int]
    current_destination_folder: Optional[str]

    processed_matches: int
    remaining_matches: int
    total_matches: int

    last_message: str
    last_error: Optional[str]

    @property
    def running(self) -> bool:
        return self.status == "running"

    @property
    def paused(self) -> bool:
        return self.status == "paused"

    @property
    def stopped(self) -> bool:
        return self.status == "stopped"

    @property
    def complete(self) -> bool:
        return self.status == "completed"

    @property
    def failed(self) -> bool:
        return self.status == "failed"

    @property
    def can_start(self) -> bool:
        return self.status in {
            "stopped",
            "completed",
            "failed",
        }

    @property
    def can_pause(self) -> bool:
        return self.status == "running"

    @property
    def can_resume(self) -> bool:
        return self.status == "paused"

    @property
    def can_stop(self) -> bool:
        return self.status in {"running", "paused"}


class HistoricalRunnerService:
    """Persist execution state for a historical capture batch."""

    def __init__(self) -> None:
        self.batch_service = HistoricalCaptureBatchService()

    def load(
        self,
        root: str | Path,
    ) -> HistoricalRunnerState:
        root_path = self._normalise_root(root)
        path = root_path / RUNNER_FILENAME

        if not path.is_file():
            return self._initial_state(root_path)

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "Historical runner state is invalid: "
                + str(exc)
            ) from exc

        state = self._from_payload(root_path, payload)

        if state.status not in RUNNER_STATUSES:
            raise ValueError(
                f"Unsupported historical runner status: "
                f"{state.status!r}"
            )

        return self._synchronise(state)

    def start(
        self,
        root: str | Path,
    ) -> HistoricalRunnerState:
        root_path = self._normalise_root(root)
        batch = self.batch_service.load(root_path)

        if batch.next_item is None:
            return self._write_state(
                root_path,
                status="completed",
                current=None,
                created_at=self._existing_created_at(root_path),
                started_at=None,
                paused_at=None,
                stopped_at=None,
                completed_at=self._now(),
                last_message=(
                    "Historical capture batch is already complete."
                ),
                last_error=None,
                processed_matches=batch.captured_matches,
                remaining_matches=batch.missing_matches,
                total_matches=batch.total_matches,
            )

        existing = self.load(root_path)

        if existing.status == "running":
            return existing

        now = self._now()

        return self._write_state(
            root_path,
            status="running",
            current=batch.next_item,
            created_at=existing.created_at,
            started_at=now,
            paused_at=None,
            stopped_at=None,
            completed_at=None,
            last_message=(
                "Historical runner started at "
                + self._item_label(batch.next_item)
                + "."
            ),
            last_error=None,
            processed_matches=batch.captured_matches,
            remaining_matches=batch.missing_matches,
            total_matches=batch.total_matches,
        )

    def pause(
        self,
        root: str | Path,
    ) -> HistoricalRunnerState:
        state = self.load(root)

        if state.status != "running":
            raise ValueError(
                "Historical runner can only be paused while running."
            )

        return self._copy_with(
            state,
            status="paused",
            paused_at=self._now(),
            last_message="Historical runner paused.",
        )

    def resume(
        self,
        root: str | Path,
    ) -> HistoricalRunnerState:
        state = self.load(root)

        if state.status != "paused":
            raise ValueError(
                "Historical runner can only resume from paused state."
            )

        batch = self.batch_service.load(state.root)

        if batch.next_item is None:
            return self._write_state(
                state.root,
                status="completed",
                current=None,
                created_at=state.created_at,
                started_at=state.started_at,
                paused_at=None,
                stopped_at=None,
                completed_at=self._now(),
                last_message="Historical capture batch is complete.",
                last_error=None,
                processed_matches=batch.captured_matches,
                remaining_matches=batch.missing_matches,
                total_matches=batch.total_matches,
            )

        return self._write_state(
            state.root,
            status="running",
            current=batch.next_item,
            created_at=state.created_at,
            started_at=state.started_at or self._now(),
            paused_at=None,
            stopped_at=None,
            completed_at=None,
            last_message=(
                "Historical runner resumed at "
                + self._item_label(batch.next_item)
                + "."
            ),
            last_error=None,
            processed_matches=batch.captured_matches,
            remaining_matches=batch.missing_matches,
            total_matches=batch.total_matches,
        )

    def stop(
        self,
        root: str | Path,
    ) -> HistoricalRunnerState:
        state = self.load(root)

        if state.status not in {"running", "paused"}:
            return state

        return self._copy_with(
            state,
            status="stopped",
            stopped_at=self._now(),
            paused_at=None,
            last_message="Historical runner stopped.",
        )

    def mark_failed(
        self,
        root: str | Path,
        error: str,
    ) -> HistoricalRunnerState:
        state = self.load(root)

        return self._copy_with(
            state,
            status="failed",
            last_message="Historical runner failed.",
            last_error=str(error),
        )

    def clear(
        self,
        root: str | Path,
    ) -> bool:
        root_path = self._normalise_root(root)
        path = root_path / RUNNER_FILENAME

        if not path.exists():
            return False

        path.unlink()
        return True

    def _synchronise(
        self,
        state: HistoricalRunnerState,
    ) -> HistoricalRunnerState:
        try:
            batch = self.batch_service.load(state.root)
        except ValueError:
            return state

        current = batch.next_item

        if current is None and state.status in {
            "running",
            "paused",
        }:
            return self._write_state(
                state.root,
                status="completed",
                current=None,
                created_at=state.created_at,
                started_at=state.started_at,
                paused_at=None,
                stopped_at=None,
                completed_at=self._now(),
                last_message="Historical capture batch is complete.",
                last_error=None,
                processed_matches=batch.captured_matches,
                remaining_matches=batch.missing_matches,
                total_matches=batch.total_matches,
            )

        if (
            state.status in {"running", "paused"}
            and current is not None
            and (
                state.current_position != current.position
                or state.current_match_id != current.next_match_id
            )
        ):
            return self._write_state(
                state.root,
                status=state.status,
                current=current,
                created_at=state.created_at,
                started_at=state.started_at,
                paused_at=state.paused_at,
                stopped_at=state.stopped_at,
                completed_at=state.completed_at,
                last_message=(
                    "Historical runner advanced to "
                    + self._item_label(current)
                    + "."
                ),
                last_error=state.last_error,
                processed_matches=batch.captured_matches,
                remaining_matches=batch.missing_matches,
                total_matches=batch.total_matches,
            )

        if (
            state.processed_matches != batch.captured_matches
            or state.remaining_matches != batch.missing_matches
            or state.total_matches != batch.total_matches
        ):
            return self._write_state(
                state.root,
                status=state.status,
                current=current,
                created_at=state.created_at,
                started_at=state.started_at,
                paused_at=state.paused_at,
                stopped_at=state.stopped_at,
                completed_at=state.completed_at,
                last_message=state.last_message,
                last_error=state.last_error,
                processed_matches=batch.captured_matches,
                remaining_matches=batch.missing_matches,
                total_matches=batch.total_matches,
            )

        return state

    def _initial_state(
        self,
        root: Path,
    ) -> HistoricalRunnerState:
        now = self._now()

        return HistoricalRunnerState(
            root=root,
            status="stopped",
            created_at=now,
            updated_at=now,
            started_at=None,
            paused_at=None,
            stopped_at=None,
            completed_at=None,
            current_position=None,
            current_series_id=None,
            current_series_label=None,
            current_week_id=None,
            current_week_label=None,
            current_group=None,
            current_match_id=None,
            current_destination_folder=None,
            processed_matches=0,
            remaining_matches=0,
            total_matches=0,
            last_message="Historical runner has not started.",
            last_error=None,
        )

    def _write_state(
        self,
        root: Path,
        *,
        status: str,
        current: Optional[HistoricalCaptureBatchItem],
        created_at: str,
        started_at: Optional[str],
        paused_at: Optional[str],
        stopped_at: Optional[str],
        completed_at: Optional[str],
        last_message: str,
        last_error: Optional[str],
        processed_matches: int,
        remaining_matches: int,
        total_matches: int,
    ) -> HistoricalRunnerState:
        state = HistoricalRunnerState(
            root=root,
            status=status,
            created_at=created_at,
            updated_at=self._now(),
            started_at=started_at,
            paused_at=paused_at,
            stopped_at=stopped_at,
            completed_at=completed_at,
            current_position=(
                current.position if current else None
            ),
            current_series_id=(
                current.series_id if current else None
            ),
            current_series_label=(
                current.series_label if current else None
            ),
            current_week_id=(
                current.week_id if current else None
            ),
            current_week_label=(
                current.week_label if current else None
            ),
            current_group=(
                current.group if current else None
            ),
            current_match_id=(
                current.next_match_id if current else None
            ),
            current_destination_folder=(
                str(current.destination_folder)
                if current
                else None
            ),
            processed_matches=processed_matches,
            remaining_matches=remaining_matches,
            total_matches=total_matches,
            last_message=last_message,
            last_error=last_error,
        )

        payload = asdict(state)
        payload["root"] = str(root)

        root.mkdir(parents=True, exist_ok=True)

        (root / RUNNER_FILENAME).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        return state

    def _copy_with(
        self,
        state: HistoricalRunnerState,
        **changes,
    ) -> HistoricalRunnerState:
        payload = asdict(state)
        payload.update(changes)

        current = None

        if state.current_position is not None:
            try:
                batch = self.batch_service.load(state.root)
                current = next(
                    (
                        item
                        for item in batch.items
                        if item.position
                        == state.current_position
                    ),
                    batch.next_item,
                )
            except ValueError:
                current = None

        return self._write_state(
            state.root,
            status=payload["status"],
            current=current,
            created_at=state.created_at,
            started_at=payload.get("started_at"),
            paused_at=payload.get("paused_at"),
            stopped_at=payload.get("stopped_at"),
            completed_at=payload.get("completed_at"),
            last_message=payload["last_message"],
            last_error=payload.get("last_error"),
            processed_matches=state.processed_matches,
            remaining_matches=state.remaining_matches,
            total_matches=state.total_matches,
        )

    def _from_payload(
        self,
        root: Path,
        payload: dict,
    ) -> HistoricalRunnerState:
        return HistoricalRunnerState(
            root=root,
            status=str(payload.get("status", "stopped")),
            created_at=str(
                payload.get("created_at") or self._now()
            ),
            updated_at=str(
                payload.get("updated_at") or self._now()
            ),
            started_at=payload.get("started_at"),
            paused_at=payload.get("paused_at"),
            stopped_at=payload.get("stopped_at"),
            completed_at=payload.get("completed_at"),
            current_position=payload.get("current_position"),
            current_series_id=payload.get(
                "current_series_id"
            ),
            current_series_label=payload.get(
                "current_series_label"
            ),
            current_week_id=payload.get("current_week_id"),
            current_week_label=payload.get(
                "current_week_label"
            ),
            current_group=payload.get("current_group"),
            current_match_id=payload.get(
                "current_match_id"
            ),
            current_destination_folder=payload.get(
                "current_destination_folder"
            ),
            processed_matches=int(
                payload.get("processed_matches", 0)
            ),
            remaining_matches=int(
                payload.get("remaining_matches", 0)
            ),
            total_matches=int(
                payload.get("total_matches", 0)
            ),
            last_message=str(
                payload.get(
                    "last_message",
                    "Historical runner has not started.",
                )
            ),
            last_error=payload.get("last_error"),
        )

    def _existing_created_at(
        self,
        root: Path,
    ) -> str:
        path = root / RUNNER_FILENAME

        if not path.is_file():
            return self._now()

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
            return str(
                payload.get("created_at") or self._now()
            )
        except (OSError, json.JSONDecodeError):
            return self._now()

    @staticmethod
    def _item_label(
        item: HistoricalCaptureBatchItem,
    ) -> str:
        return (
            f"{item.series_label} · "
            f"{item.week_label} · "
            f"{item.group} · "
            f"Match {item.next_match_id or '—'}"
        )

    @staticmethod
    def _normalise_root(
        value: str | Path,
    ) -> Path:
        text = str(value or "").strip()

        if not text:
            raise ValueError(
                "Enter a historical runner root."
            )

        return Path(text).expanduser().resolve()

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()
