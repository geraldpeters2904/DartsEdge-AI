
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.fixture_edge_service import (
    build_fixture_edge_rows,
)


@dataclass(frozen=True)
class LiveFixtureEdgeCaptureReport:
    future_fixtures: int
    bridge_ready: bool
    capture_attempted: bool
    extracted_prices: int
    stored_prices: int
    unchanged_prices: int
    skipped_prices: int
    challenge_detected: bool
    edge_rows: int
    priced_edge_rows: int
    value_rows: int
    message: str
    error: Optional[str] = None


def _future_or_current_modus_fixture_count(
    db: Session,
    *,
    today: Optional[date] = None,
) -> int:
    current_day = today or date.today()

    return int(
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= current_day,
            Match.tournament.ilike("%MODUS%"),
        )
        .count()
    )


def run_live_fixture_edge_capture(
    db: Session,
    *,
    today: Optional[date] = None,
) -> LiveFixtureEdgeCaptureReport:
    fixture_count = _future_or_current_modus_fixture_count(
        db,
        today=today,
    )

    if fixture_count == 0:
        return LiveFixtureEdgeCaptureReport(
            future_fixtures=0,
            bridge_ready=False,
            capture_attempted=False,
            extracted_prices=0,
            stored_prices=0,
            unchanged_prices=0,
            skipped_prices=0,
            challenge_detected=False,
            edge_rows=0,
            priced_edge_rows=0,
            value_rows=0,
            message=(
                "No current or future scheduled MODUS fixtures are stored; "
                "Fixture Edge has nothing to evaluate."
            ),
        )

    rows = build_fixture_edge_rows(
        db,
        today=today,
    )

    priced = sum(
        1
        for row in rows
        if row.bookmaker_odds is not None
    )

    value = sum(
        1
        for row in rows
        if row.classification in {
            "VALUE",
            "STRONG VALUE",
        }
    )

    return LiveFixtureEdgeCaptureReport(
        future_fixtures=fixture_count,
        bridge_ready=True,
        capture_attempted=False,
        extracted_prices=0,
        stored_prices=0,
        unchanged_prices=0,
        skipped_prices=0,
        challenge_detected=False,
        edge_rows=len(rows),
        priced_edge_rows=priced,
        value_rows=value,
        message=(
            "Fixture Edge refreshed from stored bookmaker prices. "
            f"{priced} priced selection row(s) available."
        ),
    )
