from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.odds_snapshot import OddsSnapshot
from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)


def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "").strip().casefold().split()
    )


def _same_market(
    row: OddsSnapshot,
    price: CapturedBookmakerPrice,
) -> bool:
    return (
        row.fixture_date == price.fixture_date
        and _normalise(row.player_a) == _normalise(price.player_a)
        and _normalise(row.player_b) == _normalise(price.player_b)
        and _normalise(row.market) == _normalise(price.market)
        and _normalise(row.selection) == _normalise(price.selection)
        and _normalise(row.bookmaker) == _normalise(price.bookmaker)
    )


def _latest_snapshot(
    db: Session,
    price: CapturedBookmakerPrice,
):
    candidates = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_date
            == price.fixture_date
        )
        .order_by(
            OddsSnapshot.captured_at.desc(),
            OddsSnapshot.id.desc(),
        )
        .all()
    )

    for row in candidates:
        if _same_market(
            row,
            price,
        ):
            return row

    return None


def store_price_changes(
    db: Session,
    prices: Iterable[
        CapturedBookmakerPrice
    ],
) -> dict:
    stored = 0
    unchanged = 0
    skipped = 0

    for price in prices:
        try:
            odds = float(
                price.decimal_odds
            )
        except (
            TypeError,
            ValueError,
        ):
            skipped += 1
            continue

        if odds <= 1.0:
            skipped += 1
            continue

        if not (
            price.player_a
            and price.player_b
            and price.selection
            and price.market
            and price.bookmaker
        ):
            skipped += 1
            continue

        latest = _latest_snapshot(
            db,
            price,
        )

        if (
            latest is not None
            and abs(
                float(
                    latest.decimal_odds
                )
                - odds
            )
            < 0.000001
        ):
            unchanged += 1
            continue

        row = OddsSnapshot(
            fixture_date=(
                price.fixture_date
            ),
            tournament=(
                price.tournament
                or "Unknown"
            ),
            player_a=price.player_a,
            player_b=price.player_b,
            market=price.market,
            selection=price.selection,
            bookmaker=price.bookmaker,
            decimal_odds=odds,
            captured_at=(
                price.captured_at
                or datetime.utcnow()
            ),
            provider_id=(
                price.provider_id
            ),
        )

        db.add(
            row
        )
        stored += 1

    if stored:
        db.commit()

    return {
        "stored": stored,
        "unchanged": unchanged,
        "skipped": skipped,
    }
