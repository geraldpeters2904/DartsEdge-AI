from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


@dataclass(frozen=True)
class LiveOpsSummary:
    generated_at: datetime
    scheduled_matches: int
    completed_matches: int
    odds_snapshots: int
    odds_movements: int
    latest_odds_at: Optional[datetime]
    latest_movement_at: Optional[datetime]
    paddy_power_ready: bool
    paddy_power_message: str
    paddy_power_function: Optional[str]


@dataclass(frozen=True)
class RecentOddsMovement:
    fixture_id: int
    bookmaker_code: str
    market: str
    selection: str
    previous_odds: float
    new_odds: float
    direction: str
    detected_at: datetime


def build_live_ops_summary(db: Session) -> LiveOpsSummary:
    scheduled_matches = (
        db.query(func.count(Match.id))
        .filter(Match.status == "scheduled")
        .scalar()
        or 0
    )

    completed_matches = (
        db.query(func.count(Match.id))
        .filter(Match.status == "completed")
        .scalar()
        or 0
    )

    odds_snapshots = db.query(func.count(OddsSnapshot.id)).scalar() or 0
    odds_movements = db.query(func.count(OddsMovement.id)).scalar() or 0

    latest_odds_at = db.query(
        func.max(OddsSnapshot.captured_at)
    ).scalar()

    latest_movement_at = db.query(
        func.max(OddsMovement.detected_at)
    ).scalar()

    health = check_paddy_power_live_health()

    return LiveOpsSummary(
        generated_at=datetime.utcnow(),
        scheduled_matches=int(scheduled_matches),
        completed_matches=int(completed_matches),
        odds_snapshots=int(odds_snapshots),
        odds_movements=int(odds_movements),
        latest_odds_at=latest_odds_at,
        latest_movement_at=latest_movement_at,
        paddy_power_ready=health.ready,
        paddy_power_message=health.message,
        paddy_power_function=health.function_name,
    )


def recent_odds_movements(
    db: Session,
    *,
    limit: int = 20,
) -> tuple[RecentOddsMovement, ...]:
    rows = (
        db.query(OddsMovement)
        .order_by(
            OddsMovement.detected_at.desc(),
            OddsMovement.id.desc(),
        )
        .limit(max(1, int(limit)))
        .all()
    )

    return tuple(
        RecentOddsMovement(
            fixture_id=int(row.fixture_id),
            bookmaker_code=str(row.bookmaker_code),
            market=str(row.market),
            selection=str(row.selection),
            previous_odds=float(row.previous_odds),
            new_odds=float(row.new_odds),
            direction=str(row.direction),
            detected_at=row.detected_at,
        )
        for row in rows
    )
