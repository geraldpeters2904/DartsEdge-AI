from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional, Tuple

from app.services.modus_historical_catalog_service import (
    ModusCatalogOption,
    ModusHistoricalCatalogService,
)


_SERIES_LABEL = re.compile(
    r"^\s*Series\s+(\d+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HistoricalArchiveSeriesItem:
    position: int
    series_id: int
    series_label: str
    folder: Path
    prepared_groups: int
    complete_groups: int
    incomplete_groups: int
    status: str

    @property
    def complete(self) -> bool:
        return self.status == "complete"


@dataclass(frozen=True)
class HistoricalArchivePlan:
    root: Path
    series: Tuple[HistoricalArchiveSeriesItem, ...]

    @property
    def discovered_series(self) -> int:
        return len(self.series)

    @property
    def complete_series(self) -> int:
        return sum(1 for item in self.series if item.complete)

    @property
    def remaining_series(self) -> int:
        return self.discovered_series - self.complete_series

    @property
    def next_series(
        self,
    ) -> Optional[HistoricalArchiveSeriesItem]:
        return next(
            (
                item
                for item in self.series
                if not item.complete
            ),
            None,
        )

    @property
    def complete(self) -> bool:
        return self.next_series is None


class HistoricalArchivePlanService:
    """
    Build a newest-to-oldest plan for numbered MODUS Super Series only.

    Non-series catalogue entries such as special events are ignored.
    Series IDs are taken directly from the rendered catalogue and are
    never assumed to be sequential.
    """

    def __init__(
        self,
        *,
        catalog_service: Optional[
            ModusHistoricalCatalogService
        ] = None,
    ) -> None:
        self.catalog_service = (
            catalog_service
            or ModusHistoricalCatalogService()
        )

    def build_plan(
        self,
        *,
        root: str | Path,
        catalog_html: str,
    ) -> HistoricalArchivePlan:
        root_path = Path(root).expanduser().resolve()
        catalog = self.catalog_service.parse(catalog_html)

        numbered_series = [
            option
            for option in catalog.series
            if self._label_number(option.label) is not None
        ]

        ordered_series = sorted(
            numbered_series,
            key=self._series_sort_key,
            reverse=True,
        )

        items = tuple(
            self._build_item(
                root=root_path,
                option=option,
                position=index,
            )
            for index, option in enumerate(
                ordered_series,
                start=1,
            )
        )

        return HistoricalArchivePlan(
            root=root_path,
            series=items,
        )

    def _build_item(
        self,
        *,
        root: Path,
        option: ModusCatalogOption,
        position: int,
    ) -> HistoricalArchiveSeriesItem:
        folder = root / f"Series_{option.value}"

        session_files = tuple(
            folder.rglob(".modus_capture_session.json")
        ) if folder.exists() else ()

        prepared_groups = len(session_files)
        complete_groups = 0
        incomplete_groups = 0

        for session_file in session_files:
            try:
                text = session_file.read_text(
                    encoding="utf-8"
                )
            except OSError:
                incomplete_groups += 1
                continue

            if self._session_complete(text):
                complete_groups += 1
            else:
                incomplete_groups += 1

        if prepared_groups == 0:
            status = "not_started"
        elif incomplete_groups:
            status = "in_progress"
        else:
            status = "complete"

        return HistoricalArchiveSeriesItem(
            position=position,
            series_id=option.value,
            series_label=option.label,
            folder=folder,
            prepared_groups=prepared_groups,
            complete_groups=complete_groups,
            incomplete_groups=incomplete_groups,
            status=status,
        )

    @staticmethod
    def _session_complete(text: str) -> bool:
        compact = "".join(
            str(text or "").lower().split()
        )

        return (
            '"complete":true' in compact
            or '"missing_count":0' in compact
        )

    @staticmethod
    def _series_sort_key(
        option: ModusCatalogOption,
    ) -> tuple:
        number = HistoricalArchivePlanService._label_number(
            option.label
        )

        return (
            number if number is not None else -1,
            option.value,
        )

    @staticmethod
    def _label_number(label: str) -> Optional[int]:
        match = _SERIES_LABEL.match(
            str(label or "")
        )

        return int(match.group(1)) if match else None
