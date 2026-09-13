from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from app.models.match import Match
from app.services.modus_import_scope_service import (
    ModusImportScope,
    find_modus_import_scope_for_match,
)


@dataclass(frozen=True)
class ScopedStaleFixture:
    fixture_id: int
    fixture_date: date
    player_a: str
    player_b: str
    stage: Optional[str]


@dataclass(frozen=True)
class StaleFixtureScopeGroup:
    scope: ModusImportScope
    fixtures: Tuple[ScopedStaleFixture, ...]


def group_stale_modus_fixtures_by_scope(
    db,
    *,
    today: Optional[date] = None,
) -> Tuple[StaleFixtureScopeGroup, ...]:
    current_day = today or date.today()

    rows = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date < current_day,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .all()
    )

    grouped = {}

    for match in rows:
        if "modus" not in str(
            match.tournament or ""
        ).casefold():
            continue

        scope = find_modus_import_scope_for_match(
            db,
            int(match.id),
        )
        if scope is None:
            continue

        key = (
            int(scope.series_id),
            int(scope.week_id),
            str(scope.group),
        )

        grouped.setdefault(
            key,
            {
                "scope": scope,
                "fixtures": [],
            },
        )

        grouped[key]["fixtures"].append(
            ScopedStaleFixture(
                fixture_id=int(match.id),
                fixture_date=match.date,
                player_a=match.player_a,
                player_b=match.player_b,
                stage=match.stage,
            )
        )

    groups = []

    for key in sorted(
        grouped,
        key=lambda value: (
            value[0],
            value[1],
            value[2],
        ),
    ):
        entry = grouped[key]
        groups.append(
            StaleFixtureScopeGroup(
                scope=entry["scope"],
                fixtures=tuple(
                    entry["fixtures"]
                ),
            )
        )

    return tuple(groups)
