from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable, List, Optional

from app.services.modus_capture_session_service import (
    ModusCaptureSession,
    ModusCaptureSessionService,
)


BATCH_FILENAME = ".dartsedge_capture_batch.json"


@dataclass(frozen=True)
class HistoricalCaptureBatchItem:
    position: int
    destination_folder: Path
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
    status: str
    retry_count: int
    last_error: Optional[str]

    @property
    def session_url(self) -> str:
        from urllib.parse import quote

        return (
            "/admin/collector/capture/modus?folder="
            + quote(str(self.destination_folder))
        )


@dataclass(frozen=True)
class HistoricalCaptureBatch:
    root: Path
    created_at: str
    updated_at: str
    items: List[HistoricalCaptureBatchItem]

    @property
    def total_groups(self) -> int:
        return len(self.items)

    @property
    def completed_groups(self) -> int:
        return sum(1 for item in self.items if item.complete)

    @property
    def remaining_groups(self) -> int:
        return self.total_groups - self.completed_groups

    @property
    def total_matches(self) -> int:
        return sum(item.expected_count for item in self.items)

    @property
    def captured_matches(self) -> int:
        return sum(item.captured_count for item in self.items)

    @property
    def missing_matches(self) -> int:
        return sum(item.missing_count for item in self.items)

    @property
    def progress_percent(self) -> int:
        if self.total_matches == 0:
            return 0

        return round(
            self.captured_matches / self.total_matches * 100
        )

    @property
    def next_item(self) -> Optional[HistoricalCaptureBatchItem]:
        return next(
            (
                item
                for item in self.items
                if not item.complete
                and item.status not in {"failed", "skipped"}
            ),
            None,
        )


class HistoricalCaptureBatchService:
    """Persist and refresh a multi-Series, multi-Week capture batch."""

    def __init__(self) -> None:
        self.session_service = ModusCaptureSessionService()

    def create(
        self,
        *,
        root: str | Path,
        results_pages: Iterable[tuple[str, str]],
    ) -> HistoricalCaptureBatch:
        root_path = self._normalise_root(root)
        root_path.mkdir(parents=True, exist_ok=True)

        entries = []
        seen = set()

        for filename, html in results_pages:
            if not (html or "").strip():
                raise ValueError(
                    f"Saved results page is blank: {filename}"
                )

            page = self.session_service.results_parser.parse_results_document(
                html
            )
            self.session_service._validate_scope(page)

            key = (
                int(page.series_id),
                int(page.week_id),
                str(page.group),
            )

            if key in seen:
                raise ValueError(
                    "Duplicate capture group supplied: "
                    f"{page.series_label} · "
                    f"{page.week_label} · "
                    f"{page.group}"
                )

            seen.add(key)

            destination = (
                root_path
                / f"Series_{page.series_id:02d}"
                / self._week_folder(page.week_label)
                / self._group_folder(page.group)
            )

            session = self._create_or_reuse_session(
                filename=filename,
                html=html,
                destination=destination,
            )

            entries.append(
                self._stored_entry(
                    session=session,
                    retry_count=0,
                    last_error=None,
                )
            )

        if not entries:
            raise ValueError(
                "Choose at least one saved MODUS results page."
            )

        entries.sort(key=self._stored_sort_key)

        now = datetime.utcnow().isoformat()

        payload = {
            "version": 1,
            "root": str(root_path),
            "created_at": now,
            "updated_at": now,
            "items": entries,
        }

        self._save_payload(root_path, payload)

        return self.load(root_path)

    def load(
        self,
        root: str | Path,
    ) -> HistoricalCaptureBatch:
        root_path = self._normalise_root(root)
        path = root_path / BATCH_FILENAME

        if not path.is_file():
            raise ValueError(
                "No historical capture batch exists for this root."
            )

        payload = json.loads(path.read_text(encoding="utf-8"))

        refreshed_items = []
        changed = False

        for stored in payload.get("items", []):
            destination = Path(
                stored["destination_folder"]
            ).expanduser().resolve()

            try:
                session = self.session_service.load_session(destination)

                refreshed = self._stored_entry(
                    session=session,
                    retry_count=int(stored.get("retry_count", 0)),
                    last_error=stored.get("last_error"),
                )

                if refreshed != stored:
                    changed = True

            except Exception as exc:
                refreshed = dict(stored)
                refreshed["status"] = "failed"
                refreshed["last_error"] = str(exc)
                refreshed["complete"] = False
                changed = True

            refreshed_items.append(refreshed)

        refreshed_items.sort(key=self._stored_sort_key)

        if changed:
            payload["items"] = refreshed_items
            payload["updated_at"] = datetime.utcnow().isoformat()
            self._save_payload(root_path, payload)

        items = [
            self._build_item(position, stored)
            for position, stored in enumerate(
                refreshed_items,
                start=1,
            )
        ]

        return HistoricalCaptureBatch(
            root=root_path,
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            items=items,
        )

    def refresh(
        self,
        root: str | Path,
    ) -> HistoricalCaptureBatch:
        return self.load(root)

    def clear(
        self,
        root: str | Path,
    ) -> bool:
        root_path = self._normalise_root(root)
        path = root_path / BATCH_FILENAME

        if not path.exists():
            return False

        path.unlink()
        return True

    def _create_or_reuse_session(
        self,
        *,
        filename: str,
        html: str,
        destination: Path,
    ) -> ModusCaptureSession:
        session_file = (
            destination
            / ".modus_capture_session.json"
        )

        if session_file.is_file():
            existing = self.session_service.load_session(destination)

            page = self.session_service.results_parser.parse_results_document(
                html
            )

            if (
                existing.series_id != page.series_id
                or existing.week_id != page.week_id
                or existing.group != page.group
            ):
                raise ValueError(
                    "Existing capture session does not match "
                    f"{page.series_label} · "
                    f"{page.week_label} · "
                    f"{page.group}"
                )

            return existing

        return self.session_service.create_session(
            results_filename=filename,
            results_html=html,
            destination_folder=destination,
        )

    @staticmethod
    def _stored_entry(
        *,
        session: ModusCaptureSession,
        retry_count: int,
        last_error: Optional[str],
    ) -> dict:
        return {
            "destination_folder": str(
                session.destination_folder
            ),
            "series_id": session.series_id,
            "series_label": session.series_label,
            "week_id": session.week_id,
            "week_label": session.week_label,
            "group": session.group,
            "expected_count": session.expected_count,
            "captured_count": session.captured_count,
            "missing_count": session.missing_count,
            "progress_percent": session.progress_percent,
            "complete": session.complete,
            "next_match_id": (
                session.next_item.match_id
                if session.next_item is not None
                else None
            ),
            "status": (
                "complete"
                if session.complete
                else "queued"
            ),
            "retry_count": retry_count,
            "last_error": last_error,
        }

    @staticmethod
    def _build_item(
        position: int,
        stored: dict,
    ) -> HistoricalCaptureBatchItem:
        return HistoricalCaptureBatchItem(
            position=position,
            destination_folder=Path(
                stored["destination_folder"]
            ),
            series_id=int(stored["series_id"]),
            series_label=str(stored["series_label"]),
            week_id=int(stored["week_id"]),
            week_label=str(stored["week_label"]),
            group=str(stored["group"]),
            expected_count=int(
                stored.get("expected_count", 0)
            ),
            captured_count=int(
                stored.get("captured_count", 0)
            ),
            missing_count=int(
                stored.get("missing_count", 0)
            ),
            progress_percent=int(
                stored.get("progress_percent", 0)
            ),
            complete=bool(stored.get("complete", False)),
            next_match_id=stored.get("next_match_id"),
            status=str(stored.get("status", "queued")),
            retry_count=int(stored.get("retry_count", 0)),
            last_error=stored.get("last_error"),
        )

    @classmethod
    def _stored_sort_key(cls, stored: dict):
        return (
            int(stored["series_id"]),
            int(stored["week_id"]),
            cls._group_order(str(stored["group"])),
        )

    @staticmethod
    def _group_order(group: str) -> int:
        return {
            "Group A": 1,
            "Group B": 2,
            "Group C": 3,
            "Final": 4,
        }.get(group, 99)

    @staticmethod
    def _week_folder(week_label: str) -> str:
        import re

        match = re.search(r"\b(\d+)\b", str(week_label or ""))

        if match is None:
            raise ValueError(
                f"Could not determine display week from label: {week_label!r}"
            )

        display_week = int(match.group(1))

        if display_week <= 0:
            raise ValueError(
                f"Display week must be positive: {week_label!r}"
            )

        return f"Week_{display_week:02d}"

    @staticmethod
    def _group_folder(group: str) -> str:
        return {
            "Group A": "Group_A",
            "Group B": "Group_B",
            "Group C": "Group_C",
            "Final": "Final",
        }[group]

    @staticmethod
    def _normalise_root(value: str | Path) -> Path:
        text = str(value or "").strip()

        if not text:
            raise ValueError("Enter a capture batch root.")

        return Path(text).expanduser().resolve()

    @staticmethod
    def _save_payload(
        root: Path,
        payload: dict,
    ) -> None:
        path = root / BATCH_FILENAME
        path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
