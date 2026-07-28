from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional

from app.providers.adapters.modus_official.parser import ModusSavedPageParser
from app.providers.adapters.modus_official.urls import ModusUrlModel


SESSION_FILENAME = ".modus_capture_session.json"


@dataclass(frozen=True)
class ModusCaptureQueueItem:
    match_id: int
    match_number: Optional[int]
    player_a_name: str
    player_b_name: str
    player_a_legs: Optional[int]
    player_b_legs: Optional[int]
    source_url: str
    destination_filename: str
    captured: bool


@dataclass(frozen=True)
class ModusCaptureSession:
    destination_folder: Path
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    group: str
    results_source_filename: str
    created_at: datetime
    updated_at: datetime
    items: List[ModusCaptureQueueItem] = field(default_factory=list)

    @property
    def expected_count(self) -> int:
        return len(self.items)

    @property
    def captured_count(self) -> int:
        return sum(1 for item in self.items if item.captured)

    @property
    def missing_count(self) -> int:
        return self.expected_count - self.captured_count

    @property
    def complete(self) -> bool:
        return bool(self.items) and self.missing_count == 0

    @property
    def next_item(self) -> Optional[ModusCaptureQueueItem]:
        return next((item for item in self.items if not item.captured), None)

    def to_dict(self) -> dict:
        return {
            "destination_folder": str(self.destination_folder),
            "series_id": self.series_id,
            "series_label": self.series_label,
            "week_id": self.week_id,
            "week_label": self.week_label,
            "group": self.group,
            "results_source_filename": self.results_source_filename,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expected_count": self.expected_count,
            "captured_count": self.captured_count,
            "missing_count": self.missing_count,
            "complete": self.complete,
            "next_match_id": (
                self.next_item.match_id if self.next_item is not None else None
            ),
            "items": [asdict(item) for item in self.items],
        }


class ModusCaptureSessionService:
    """
    Build and persist a browser-assisted MODUS capture queue.

    This service performs no HTTP requests. It reads a saved results page,
    creates a standard capture folder and tracks which match HTML files have
    been saved manually.
    """

    def __init__(self):
        self.results_parser = ModusSavedPageParser()
        self.urls = ModusUrlModel()

    def create_session(
        self,
        *,
        results_filename: str,
        results_html: str,
        destination_folder: str | Path,
    ) -> ModusCaptureSession:
        if not (results_html or "").strip():
            raise ValueError("Saved MODUS results page is blank.")

        destination = self._normalise_destination(destination_folder)
        destination.mkdir(parents=True, exist_ok=True)

        page = self.results_parser.parse_results_document(results_html)
        self._validate_scope(page)

        results_path = destination / "results.html"
        results_path.write_text(results_html, encoding="utf-8")

        now = datetime.utcnow()
        session = self._build_session(
            destination=destination,
            page=page,
            source_filename=(results_filename or "results.html").strip(),
            created_at=now,
            updated_at=now,
        )
        self._save(session)
        return session

    def refresh_session(
        self,
        destination_folder: str | Path,
    ) -> ModusCaptureSession:
        destination = self._normalise_destination(destination_folder)
        session_path = destination / SESSION_FILENAME
        results_path = destination / "results.html"

        if not session_path.exists():
            raise ValueError(
                "No MODUS capture session exists in this folder."
            )
        if not results_path.exists():
            raise ValueError(
                "The capture folder is missing results.html."
            )

        stored = json.loads(session_path.read_text(encoding="utf-8"))
        page = self.results_parser.parse_results_document(
            results_path.read_text(encoding="utf-8")
        )

        created_at = datetime.fromisoformat(stored["created_at"])
        session = self._build_session(
            destination=destination,
            page=page,
            source_filename=stored.get(
                "results_source_filename",
                "results.html",
            ),
            created_at=created_at,
            updated_at=datetime.utcnow(),
        )
        self._save(session)
        return session

    def load_session(
        self,
        destination_folder: str | Path,
    ) -> ModusCaptureSession:
        return self.refresh_session(destination_folder)

    def _build_session(
        self,
        *,
        destination: Path,
        page,
        source_filename: str,
        created_at: datetime,
        updated_at: datetime,
    ) -> ModusCaptureSession:
        items = []

        for match in page.matches:
            filename = f"match_{match.match_id}.html"
            items.append(
                ModusCaptureQueueItem(
                    match_id=match.match_id,
                    match_number=match.match_number,
                    player_a_name=match.player_a_name,
                    player_b_name=match.player_b_name,
                    player_a_legs=match.player_a_legs,
                    player_b_legs=match.player_b_legs,
                    source_url=self.urls.match_stats_url(match.match_id),
                    destination_filename=filename,
                    captured=(destination / filename).exists(),
                )
            )

        return ModusCaptureSession(
            destination_folder=destination,
            series_id=page.series_id,
            series_label=page.series_label,
            week_id=page.week_id,
            week_label=page.week_label,
            group=page.group,
            results_source_filename=source_filename,
            created_at=created_at,
            updated_at=updated_at,
            items=items,
        )

    @staticmethod
    def _validate_scope(page) -> None:
        if not (
            page.series_id == 14
            and page.week_id == 165
            and page.group == "Group A"
        ):
            raise ValueError(
                "Sprint 3.4A1 supports only Series 14, Week 1, Group A."
            )

    @staticmethod
    def _normalise_destination(value: str | Path) -> Path:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Enter a destination folder.")
        return Path(text).expanduser().resolve()

    @staticmethod
    def _save(session: ModusCaptureSession) -> None:
        path = session.destination_folder / SESSION_FILENAME
        path.write_text(
            json.dumps(session.to_dict(), indent=2),
            encoding="utf-8",
        )
