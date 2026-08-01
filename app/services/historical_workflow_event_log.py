from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import List, Optional


EVENT_LOG_FILENAME = ".historical_workflow_events.jsonl"


@dataclass(frozen=True)
class HistoricalWorkflowEvent:
    timestamp: str
    event_type: str
    level: str
    message: str

    match_id: Optional[int] = None
    series_id: Optional[int] = None
    week_id: Optional[int] = None
    group: Optional[str] = None
    provider: Optional[str] = None
    attempt: Optional[int] = None
    error: Optional[str] = None


class HistoricalWorkflowEventLog:
    """Append-only structured workflow event log."""

    def append(
        self,
        root: str | Path,
        *,
        event_type: str,
        message: str,
        level: str = "info",
        match_id: Optional[int] = None,
        series_id: Optional[int] = None,
        week_id: Optional[int] = None,
        group: Optional[str] = None,
        provider: Optional[str] = None,
        attempt: Optional[int] = None,
        error: Optional[str] = None,
    ) -> HistoricalWorkflowEvent:
        root_path = self._normalise_root(root)

        normalised_type = str(
            event_type or ""
        ).strip().upper()

        if not normalised_type:
            raise ValueError(
                "Workflow event type is required."
            )

        normalised_message = str(
            message or ""
        ).strip()

        if not normalised_message:
            raise ValueError(
                "Workflow event message is required."
            )

        normalised_level = str(
            level or "info"
        ).strip().casefold()

        if normalised_level not in {
            "info",
            "warning",
            "error",
        }:
            raise ValueError(
                "Workflow event level must be "
                "info, warning or error."
            )

        event = HistoricalWorkflowEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=normalised_type,
            level=normalised_level,
            message=normalised_message,
            match_id=match_id,
            series_id=series_id,
            week_id=week_id,
            group=group,
            provider=provider,
            attempt=attempt,
            error=error,
        )

        root_path.mkdir(parents=True, exist_ok=True)

        path = root_path / EVENT_LOG_FILENAME

        with path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(asdict(event))
                + "\n"
            )

        return event

    def read(
        self,
        root: str | Path,
        *,
        limit: int = 100,
    ) -> List[HistoricalWorkflowEvent]:
        if limit <= 0:
            return []

        path = (
            self._normalise_root(root)
            / EVENT_LOG_FILENAME
        )

        if not path.is_file():
            return []

        events = []

        for line_number, line in enumerate(
            path.read_text(
                encoding="utf-8"
            ).splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Historical workflow event log is invalid "
                    f"at line {line_number}: {exc}"
                ) from exc

            events.append(
                HistoricalWorkflowEvent(
                    timestamp=str(
                        payload["timestamp"]
                    ),
                    event_type=str(
                        payload["event_type"]
                    ),
                    level=str(payload["level"]),
                    message=str(payload["message"]),
                    match_id=payload.get("match_id"),
                    series_id=payload.get("series_id"),
                    week_id=payload.get("week_id"),
                    group=payload.get("group"),
                    provider=payload.get("provider"),
                    attempt=payload.get("attempt"),
                    error=payload.get("error"),
                )
            )

        return events[-limit:]

    def clear(
        self,
        root: str | Path,
    ) -> bool:
        path = (
            self._normalise_root(root)
            / EVENT_LOG_FILENAME
        )

        if not path.exists():
            return False

        path.unlink()
        return True

    @staticmethod
    def _normalise_root(
        value: str | Path,
    ) -> Path:
        text = str(value or "").strip()

        if not text:
            raise ValueError(
                "Enter a historical workflow root."
            )

        return Path(text).expanduser().resolve()
