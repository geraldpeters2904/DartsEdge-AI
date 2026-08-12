from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


@dataclass(frozen=True)
class OddsAcquisitionReadiness:
    state: str
    ready: bool
    waiting: bool
    error: bool
    future_scheduled: int
    priced_fixtures: int
    current_prices: int
    bookmaker_ready: bool
    bookmaker_error: Optional[str]
    explanation: str


def build_odds_acquisition_readiness(
    db: Session,
) -> OddsAcquisitionReadiness:
    today = date.today()

    fixtures = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= today,
            Match.tournament.ilike("%MODUS%"),
        )
        .all()
    )

    fixture_ids = [
        int(item.id)
        for item in fixtures
    ]

    health = check_paddy_power_live_health()

    if not health.ready:
        return OddsAcquisitionReadiness(
            state="ERROR",
            ready=False,
            waiting=False,
            error=True,
            future_scheduled=len(fixtures),
            priced_fixtures=0,
            current_prices=0,
            bookmaker_ready=False,
            bookmaker_error=health.error,
            explanation=(
                "The Paddy Power live capture bridge "
                "is not ready."
            ),
        )

    if not fixture_ids:
        return OddsAcquisitionReadiness(
            state="WAITING_FOR_FIXTURES",
            ready=False,
            waiting=True,
            error=False,
            future_scheduled=0,
            priced_fixtures=0,
            current_prices=0,
            bookmaker_ready=True,
            bookmaker_error=None,
            explanation=(
                "The bookmaker capture path is ready, "
                "but there are no current or future "
                "scheduled MODUS fixtures to price."
            ),
        )

    prices = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id.in_(
                fixture_ids
            ),
            OddsSnapshot.market
            == "match_winner",
        )
        .all()
    )

    priced_fixture_ids = {
        int(item.fixture_id)
        for item in prices
        if item.fixture_id is not None
    }

    if not prices:
        return OddsAcquisitionReadiness(
            state="WAITING_FOR_ODDS",
            ready=False,
            waiting=True,
            error=False,
            future_scheduled=len(fixtures),
            priced_fixtures=0,
            current_prices=0,
            bookmaker_ready=True,
            bookmaker_error=None,
            explanation=(
                "Current or future MODUS fixtures "
                "exist, but no match-winner prices "
                "have been captured for them yet."
            ),
        )

    return OddsAcquisitionReadiness(
        state="READY",
        ready=True,
        waiting=False,
        error=False,
        future_scheduled=len(fixtures),
        priced_fixtures=len(
            priced_fixture_ids
        ),
        current_prices=len(prices),
        bookmaker_ready=True,
        bookmaker_error=None,
        explanation=(
            "Current MODUS fixtures have match-winner "
            "prices available in the odds warehouse."
        ),
    )
