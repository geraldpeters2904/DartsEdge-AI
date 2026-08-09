from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.match import Match


@dataclass(frozen=True)
class UpcomingFixtureIntelligence:
    fixture_id: int
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    player_a_history_matches: int
    player_b_history_matches: int
    minimum_history_matches: int
    history_ready: bool
    readiness_label: str


def _history_count(
    db: Session,
    *,
    player_name: str,
    before_date: Optional[date] = None,
) -> int:
    query = (
        db.query(Match)
        .filter(
            Match.status == "completed",
            or_(
                Match.player_a == player_name,
                Match.player_b == player_name,
            ),
        )
    )

    if before_date is not None:
        query = query.filter(
            Match.date < before_date
        )

    return int(
        query.count()
    )


def build_upcoming_fixture_intelligence(
    db: Session,
    *,
    competition_keyword: str = "MODUS",
    minimum_history_matches: int = 20,
    limit: int = 100,
    today: Optional[date] = None,
) -> tuple[UpcomingFixtureIntelligence, ...]:
    keyword = str(
        competition_keyword
        or "MODUS"
    ).strip()

    current_day = (
        today
        or date.today()
    )

    query = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= current_day,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
    )

    rows = query.limit(
        max(
            1,
            int(limit),
        )
    ).all()

    output = []

    for row in rows:
        tournament = (
            row.tournament
            or ""
        )

        if (
            keyword
            and keyword.casefold()
            not in tournament.casefold()
        ):
            continue

        player_a_history = _history_count(
            db,
            player_name=row.player_a,
            before_date=row.date,
        )

        player_b_history = _history_count(
            db,
            player_name=row.player_b,
            before_date=row.date,
        )

        minimum_history = min(
            player_a_history,
            player_b_history,
        )

        ready = (
            minimum_history
            >= int(
                minimum_history_matches
            )
        )

        if ready:
            label = "READY"
        elif minimum_history >= 10:
            label = "LIMITED"
        else:
            label = "THIN"

        output.append(
            UpcomingFixtureIntelligence(
                fixture_id=int(
                    row.id
                ),
                fixture_date=row.date,
                tournament=tournament,
                player_a=row.player_a,
                player_b=row.player_b,
                player_a_history_matches=(
                    player_a_history
                ),
                player_b_history_matches=(
                    player_b_history
                ),
                minimum_history_matches=(
                    minimum_history
                ),
                history_ready=ready,
                readiness_label=label,
            )
        )

    return tuple(
        output
    )
