
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.fixture_edge_service import (
    build_fixture_edge_rows,
)
from app.services.paddy_power_live_capture import (
    build_paddy_power_capture_once,
)
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
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
                "live odds capture was not attempted."
            ),
        )

    health = check_paddy_power_live_health()

    if not health.ready:
        return LiveFixtureEdgeCaptureReport(
            future_fixtures=fixture_count,
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
            message="Paddy Power live bridge is not ready.",
            error=health.error,
        )

    capture_once, service = build_paddy_power_capture_once()

    try:
        capture = capture_once(db)
    except Exception as exc:
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()

        return LiveFixtureEdgeCaptureReport(
            future_fixtures=fixture_count,
            bridge_ready=True,
            capture_attempted=True,
            extracted_prices=0,
            stored_prices=0,
            unchanged_prices=0,
            skipped_prices=0,
            challenge_detected=False,
            edge_rows=0,
            priced_edge_rows=0,
            value_rows=0,
            message="Paddy Power live odds capture failed.",
            error=str(exc),
        )
    finally:
        service.close()

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
        capture_attempted=True,
        extracted_prices=int(capture.extracted_prices),
        stored_prices=int(capture.stored_prices),
        unchanged_prices=int(capture.unchanged_prices),
        skipped_prices=int(capture.skipped_prices),
        challenge_detected=bool(capture.challenge_detected),
        edge_rows=len(rows),
        priced_edge_rows=priced,
        value_rows=value,
        message=(
            capture.message
            + f" Fixture Edge now has {priced} priced selection row(s)."
        ),
    )
