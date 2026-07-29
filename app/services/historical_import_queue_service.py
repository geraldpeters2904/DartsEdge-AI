from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.services.historical_import_manager_service import (
    HistoricalImportFolder,
    HistoricalImportManagerService,
)

QUEUE_FILENAME = ".dartsedge_historical_import_queue.json"

@dataclass(frozen=True)
class HistoricalImportQueueItem:
    position: int
    folder: HistoricalImportFolder
    queued_path: Path

    @property
    def complete(self) -> bool:
        return self.folder.status == "imported"

    @property
    def open_import_url(self) -> str:
        return "/admin/collector/import?source_path=" + quote(str(self.queued_path))

@dataclass(frozen=True)
class HistoricalImportQueue:
    root: Path
    created_at: str
    items: List[HistoricalImportQueueItem]

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
    def next_item(self) -> Optional[HistoricalImportQueueItem]:
        return next((item for item in self.items if not item.complete), None)

    @property
    def progress_percent(self) -> int:
        return 0 if self.total_count == 0 else round(self.completed_count / self.total_count * 100)

class HistoricalImportQueueService:
    """Persist a user-selected queue without automatically committing data."""

    def __init__(self):
        self.manager = HistoricalImportManagerService()

    def create(self, *, root: str | Path, selected_folders: List[str]) -> Path:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Historical import root is not a folder: {root_path}")

        selected, seen = [], set()
        for value in selected_folders:
            folder = Path(value).expanduser().resolve()
            try:
                folder.relative_to(root_path)
            except ValueError as exc:
                raise ValueError(f"Queue folder is outside the selected root: {folder}") from exc
            if not folder.is_dir():
                raise ValueError(f"Queue folder does not exist: {folder}")
            if not (folder / "results.html").is_file():
                raise ValueError(f"Queue folder has no results.html: {folder}")
            if str(folder) not in seen:
                selected.append(str(folder)); seen.add(str(folder))

        if not selected:
            raise ValueError("Select at least one discovered historical folder.")

        payload = {
            "version": 1,
            "root": str(root_path),
            "created_at": datetime.utcnow().isoformat(),
            "folders": selected,
        }
        path = root_path / QUEUE_FILENAME
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, db: Session, root: str | Path) -> HistoricalImportQueue:
        root_path = Path(root).expanduser().resolve()
        path = root_path / QUEUE_FILENAME
        if not path.is_file():
            raise ValueError("No historical import queue exists for this root.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        scanned = self.manager.scan(db, root_path)
        by_path = {str(item.folder.resolve()): item for item in scanned.folders}
        items = []
        for index, value in enumerate(payload.get("folders", []), start=1):
            queued = Path(value).expanduser().resolve()
            folder = by_path.get(str(queued)) or HistoricalImportFolder(
                folder=queued, manifest=None, status="error", imported_count=0,
                error_message="Folder is no longer discoverable or results.html was removed.",
            )
            items.append(HistoricalImportQueueItem(index, folder, queued))
        return HistoricalImportQueue(root_path, str(payload.get("created_at", "")), items)

    def clear(self, root: str | Path) -> bool:
        path = Path(root).expanduser().resolve() / QUEUE_FILENAME
        if not path.exists(): return False
        path.unlink(); return True
