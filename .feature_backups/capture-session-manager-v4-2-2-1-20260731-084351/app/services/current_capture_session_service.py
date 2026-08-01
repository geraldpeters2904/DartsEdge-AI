from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.services.capture_library_service import (
    CaptureLibraryEntry,
    CaptureLibraryService,
    DEFAULT_CAPTURE_ROOT,
)


class CurrentCaptureSessionService:
    """Locate the most recently updated unfinished MODUS capture session."""

    def __init__(self) -> None:
        self.library_service = CaptureLibraryService()

    def latest_incomplete(
        self,
        root: str | Path = DEFAULT_CAPTURE_ROOT,
    ) -> Optional[CaptureLibraryEntry]:
        library = self.library_service.scan(root)
        unfinished = [entry for entry in library.entries if not entry.complete]
        if not unfinished:
            return None
        return max(unfinished, key=lambda entry: entry.updated_at)
