from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
    SESSION_FILENAME,
)


DEFAULT_CAPTURE_ROOT = Path(
    "~/Documents/DartsEdge/Imports"
).expanduser()


@dataclass(frozen=True)
class CaptureLibraryEntry:
    folder: Path
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    group: str
    expected_count: int
    captured_count: int
    missing_count: int
    progress_percent: int
    complete: bool
    next_match_id: Optional[int]
    updated_at: datetime

    @property
    def resume_url(self) -> str:
        from urllib.parse import quote

        return (
            "/admin/collector/capture/modus?folder="
            + quote(str(self.folder))
        )


@dataclass(frozen=True)
class CaptureLibrarySummary:
    sessions: int
    complete_sessions: int
    in_progress_sessions: int
    expected_matches: int
    captured_matches: int
    missing_matches: int


@dataclass(frozen=True)
class CaptureLibrary:
    root: Path
    entries: List[CaptureLibraryEntry]
    summary: CaptureLibrarySummary


class CaptureLibraryService:
    """Discover persisted MODUS capture sessions below a capture root."""

    def __init__(self):
        self.session_service = ModusCaptureSessionService()

    def scan(
        self,
        root: str | Path = DEFAULT_CAPTURE_ROOT,
    ) -> CaptureLibrary:
        capture_root = Path(root).expanduser().resolve()

        if not capture_root.exists():
            capture_root.mkdir(parents=True, exist_ok=True)

        if not capture_root.is_dir():
            raise ValueError(
                f"Capture library root is not a folder: {capture_root}"
            )

        entries: List[CaptureLibraryEntry] = []

        for session_file in sorted(
            capture_root.rglob(SESSION_FILENAME)
        ):
            folder = session_file.parent

            try:
                session = self.session_service.load_session(folder)
            except Exception:
                continue

            entries.append(
                CaptureLibraryEntry(
                    folder=folder,
                    series_id=session.series_id,
                    series_label=session.series_label,
                    week_id=session.week_id,
                    week_label=session.week_label,
                    group=session.group,
                    expected_count=session.expected_count,
                    captured_count=session.captured_count,
                    missing_count=session.missing_count,
                    progress_percent=session.progress_percent,
                    complete=session.complete,
                    next_match_id=(
                        session.next_item.match_id
                        if session.next_item is not None
                        else None
                    ),
                    updated_at=session.updated_at,
                )
            )

        entries.sort(
            key=lambda entry: (
                entry.series_id,
                entry.week_id,
                self._group_order(entry.group),
            )
        )

        summary = CaptureLibrarySummary(
            sessions=len(entries),
            complete_sessions=sum(
                1 for entry in entries if entry.complete
            ),
            in_progress_sessions=sum(
                1 for entry in entries if not entry.complete
            ),
            expected_matches=sum(
                entry.expected_count for entry in entries
            ),
            captured_matches=sum(
                entry.captured_count for entry in entries
            ),
            missing_matches=sum(
                entry.missing_count for entry in entries
            ),
        )

        return CaptureLibrary(
            root=capture_root,
            entries=entries,
            summary=summary,
        )

    @staticmethod
    def _group_order(group: str) -> int:
        return {
            "Group A": 1,
            "Group B": 2,
            "Group C": 3,
            "Final": 4,
        }.get(group, 99)
