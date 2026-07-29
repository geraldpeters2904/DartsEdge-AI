from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.historical_import_manager_service import (
    HistoricalImportManagerService,
)
from app.services.historical_import_queue_service import (
    HistoricalImportQueueService,
)


ENGINE_FILENAME = ".dartsedge_historical_import_engine.json"
AUDIT_FILENAME = ".dartsedge_historical_import_audit.jsonl"


@dataclass(frozen=True)
class EngineItem:
    position: int
    folder: object
    state: str
    attempts: int
    message: str | None

    @property
    def complete(self) -> bool:
        return self.folder.status == "imported" or self.state == "completed"


@dataclass(frozen=True)
class EngineState:
    root: Path
    status: str
    created_at: str
    updated_at: str
    items: List[EngineItem]

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def completed_count(self) -> int:
        return sum(1 for item in self.items if item.complete)

    @property
    def remaining_count(self) -> int:
        return self.total_count - self.completed_count

    @property
    def progress_percent(self) -> int:
        return (
            round(self.completed_count / self.total_count * 100)
            if self.total_count else 0
        )

    @property
    def next_item(self) -> Optional[EngineItem]:
        return next(
            (
                item for item in self.items
                if not item.complete and item.state != "skipped"
            ),
            None,
        )


class HistoricalImportEngineService:
    """Resume-safe planner that preserves explicit preview and commit approval."""

    def __init__(self):
        self.manager = HistoricalImportManagerService()
        self.queue = HistoricalImportQueueService()

    def start(self, db: Session, root: str | Path) -> EngineState:
        root_path = Path(root).expanduser().resolve()
        queue = self.queue.load(db, root_path)
        now = datetime.utcnow().isoformat()
        payload = {
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "items": [
                {
                    "folder": str(item.queued_path),
                    "state": "completed" if item.complete else "pending",
                    "attempts": 0,
                    "message": "Already imported." if item.complete else None,
                }
                for item in queue.items
            ],
        }
        self._state_path(root_path).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        self._audit(root_path, "engine_started", {"groups": len(payload["items"])})
        return self.load(db, root_path)

    def load(self, db: Session, root: str | Path) -> EngineState:
        root_path = Path(root).expanduser().resolve()
        path = self._state_path(root_path)
        if not path.is_file():
            raise ValueError("No Historical Import Engine run exists for this root.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        library = self.manager.scan(db, root_path)
        by_path = {str(item.folder.resolve()): item for item in library.folders}
        items = []
        changed = False

        for index, stored in enumerate(payload["items"], start=1):
            folder = by_path.get(str(Path(stored["folder"]).resolve()))
            if folder is None:
                continue

            if folder.status == "imported" and stored["state"] != "completed":
                stored["state"] = "completed"
                stored["message"] = "Warehouse mappings confirm completion."
                changed = True
                self._audit(root_path, "group_completed", {"folder": str(folder.folder)})

            items.append(
                EngineItem(
                    position=index,
                    folder=folder,
                    state=stored["state"],
                    attempts=int(stored.get("attempts", 0)),
                    message=stored.get("message"),
                )
            )

        if items and all(item.complete for item in items):
            payload["status"] = "completed"
            changed = True

        if changed:
            payload["updated_at"] = datetime.utcnow().isoformat()
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        return EngineState(
            root=root_path,
            status=payload["status"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            items=items,
        )

    def begin_next(self, db: Session, root: str | Path) -> EngineState:
        root_path = Path(root).expanduser().resolve()
        state = self.load(db, root_path)
        if state.next_item is None:
            return state

        payload = json.loads(self._state_path(root_path).read_text(encoding="utf-8"))
        stored = payload["items"][state.next_item.position - 1]
        stored["state"] = "in_progress"
        stored["attempts"] = int(stored.get("attempts", 0)) + 1
        stored["message"] = "Opened in Import Wizard."
        payload["updated_at"] = datetime.utcnow().isoformat()
        self._state_path(root_path).write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        self._audit(
            root_path,
            "group_started",
            {"folder": stored["folder"], "attempt": stored["attempts"]},
        )
        return self.load(db, root_path)

    def audit(self, root: str | Path) -> list[dict]:
        path = self._audit_path(Path(root).expanduser().resolve())
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return list(reversed(rows[-200:]))

    @staticmethod
    def _state_path(root: Path) -> Path:
        return root / ENGINE_FILENAME

    @staticmethod
    def _audit_path(root: Path) -> Path:
        return root / AUDIT_FILENAME

    def _audit(self, root: Path, event: str, payload: dict) -> None:
        row = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "payload": payload,
        }
        with self._audit_path(root).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
