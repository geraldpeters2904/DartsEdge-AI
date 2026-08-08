from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.bookmaker import Bookmaker
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot


@dataclass(frozen=True)
class OddsRecordResult:
    snapshot_created: bool
    movement_created: bool
    snapshot_id: Optional[int]
    movement_id: Optional[int]
    message: str


def implied_probability(
    decimal_odds: float,
) -> float:
    value = float(decimal_odds)

    if value <= 1.0:
        raise ValueError(
            "Decimal odds must be greater than 1.0."
        )

    return round(
        100.0 / value,
        4,
    )


def ensure_bookmaker(
    db: Session,
    *,
    code: str,
    name: str,
    priority: int = 100,
) -> Bookmaker:
    normalised = code.strip().lower()

    row = (
        db.query(Bookmaker)
        .filter(Bookmaker.code == normalised)
        .first()
    )

    if row is not None:
        return row

    row = Bookmaker(
        code=normalised,
        name=name.strip(),
        priority=int(priority),
        enabled=True,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _latest_snapshot(
    db: Session,
    *,
    fixture_id: int,
    bookmaker_code: str,
    market: str,
    selection: str,
) -> Optional[OddsSnapshot]:
    return (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == int(fixture_id),
            OddsSnapshot.bookmaker_code == bookmaker_code,
            OddsSnapshot.market == market,
            OddsSnapshot.selection == selection,
        )
        .order_by(
            OddsSnapshot.captured_at.desc(),
            OddsSnapshot.id.desc(),
        )
        .first()
    )


def record_odds(
    db: Session,
    *,
    fixture_id: int,
    bookmaker_code: str,
    market: str,
    selection: str,
    decimal_odds: float,
    captured_at: Optional[datetime] = None,
    source_reference: Optional[str] = None,
    minimum_change: float = 0.001,
) -> OddsRecordResult:
    code = bookmaker_code.strip().lower()
    market_name = market.strip().lower()
    selection_name = selection.strip()
    price = float(decimal_odds)

    previous = _latest_snapshot(
        db,
        fixture_id=fixture_id,
        bookmaker_code=code,
        market=market_name,
        selection=selection_name,
    )

    if (
        previous is not None
        and abs(
            float(previous.decimal_odds)
            - price
        ) < float(minimum_change)
    ):
        return OddsRecordResult(
            snapshot_created=False,
            movement_created=False,
            snapshot_id=previous.id,
            movement_id=None,
            message="Odds unchanged; no new snapshot recorded.",
        )

    snapshot = OddsSnapshot(
        fixture_id=int(fixture_id),
        bookmaker_code=code,
        market=market_name,
        selection=selection_name,
        decimal_odds=price,
        implied_probability=implied_probability(price),
        captured_at=captured_at or datetime.utcnow(),
        source_reference=source_reference,
    )

    db.add(snapshot)
    db.flush()

    movement = None

    if previous is not None:
        absolute_change = round(
            price - float(previous.decimal_odds),
            6,
        )

        percentage_change = round(
            (
                absolute_change
                / float(previous.decimal_odds)
            )
            * 100.0,
            4,
        )

        movement = OddsMovement(
            fixture_id=int(fixture_id),
            bookmaker_code=code,
            market=market_name,
            selection=selection_name,
            previous_odds=float(previous.decimal_odds),
            new_odds=price,
            absolute_change=absolute_change,
            percentage_change=percentage_change,
            direction=(
                "drifting"
                if price > float(previous.decimal_odds)
                else "shortening"
            ),
            detected_at=snapshot.captured_at,
        )

        db.add(movement)
        db.flush()

    db.commit()

    return OddsRecordResult(
        snapshot_created=True,
        movement_created=movement is not None,
        snapshot_id=snapshot.id,
        movement_id=movement.id if movement else None,
        message=(
            "Odds snapshot and movement recorded."
            if movement is not None
            else "Initial odds snapshot recorded."
        ),
    )
