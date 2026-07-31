from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.historical_import_engine_service import (
    EngineState,
    HistoricalImportEngineService,
)
from app.services.historical_import_queue_service import (
    HistoricalImportQueue,
    HistoricalImportQueueService,
)


@dataclass(frozen=True)
class ImportPipeline:
    root: Path
    queue: Optional[HistoricalImportQueue]
    engine: Optional[EngineState]

    @property
    def queue_exists(self) -> bool:
        return self.queue is not None

    @property
    def engine_exists(self) -> bool:
        return self.engine is not None

    @property
    def next_queue_item(self):
        if self.queue is None:
            return None
        return self.queue.next_item

    @property
    def next_engine_item(self):
        if self.engine is None:
            return None
        return self.engine.next_item


class ImportPipelineService:
    """Read-only combined view of historical queue and engine state."""

    def __init__(self) -> None:
        self.queue_service = HistoricalImportQueueService()
        self.engine_service = HistoricalImportEngineService()

    def build(
        self,
        db: Session,
        root: str | Path,
    ) -> ImportPipeline:
        root_path = Path(root).expanduser().resolve()

        queue = None
        engine = None

        try:
            queue = self.queue_service.load(db, root_path)
        except ValueError:
            queue = None

        try:
            engine = self.engine_service.load(db, root_path)
        except ValueError:
            engine = None

        return ImportPipeline(
            root=root_path,
            queue=queue,
            engine=engine,
        )
