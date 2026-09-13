from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass(frozen=True)
class ModusImportScope:
    series_id: int
    week_id: int
    group: str


_FILENAME_RE = re.compile(
    r"^modus-series-(?P<series_id>\d+)-"
    r"week-(?P<week_id>\d+)-"
    r"(?P<group>Group [ABC]|Final)\.html$",
    re.IGNORECASE,
)


def parse_modus_import_scope(
    filename: str,
) -> Optional[ModusImportScope]:
    match = _FILENAME_RE.match(
        str(filename or "").strip()
    )
    if match is None:
        return None

    raw_group = match.group("group").strip()
    if raw_group.casefold() == "final":
        group = "Final"
    else:
        group = "Group " + raw_group[-1].upper()

    return ModusImportScope(
        series_id=int(match.group("series_id")),
        week_id=int(match.group("week_id")),
        group=group,
    )

def find_modus_import_scope_for_match(
    db,
    internal_match_id: int,
) -> Optional[ModusImportScope]:
    from app.models.historical_import import (
        HistoricalImportBatch,
        HistoricalImportItem,
    )

    rows = (
        db.query(
            HistoricalImportItem,
            HistoricalImportBatch,
        )
        .join(
            HistoricalImportBatch,
            HistoricalImportBatch.id
            == HistoricalImportItem.batch_id,
        )
        .filter(
            HistoricalImportItem.internal_id
            == int(internal_match_id),
            HistoricalImportItem.entity_type.in_(
                ("match", "fixture")
            ),
            HistoricalImportBatch.provider
            == "modus-official",
        )
        .order_by(
            HistoricalImportItem.created_at.desc(),
            HistoricalImportItem.id.desc(),
        )
        .all()
    )

    for _, batch in rows:
        scope = parse_modus_import_scope(
            batch.filename
        )
        if scope is not None:
            return scope

    return None
