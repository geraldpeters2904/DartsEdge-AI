from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from app.models.odds_snapshot import OddsSnapshot


BOOKMAKER_ALIASES = {
    "paddy power": "Paddy Power",
    "paddypower": "Paddy Power",
    "paddy-power": "Paddy Power",
    "bet365": "Bet365",
    "bet 365": "Bet365",
}


@dataclass(frozen=True)
class PricePoint:
    bookmaker: str
    decimal_odds: float
    captured_at: datetime


@dataclass(frozen=True)
class PriceLifecycle:
    fixture_date: object
    tournament: str
    player_a: str
    player_b: str
    market: str
    selection: str

    opening: PricePoint
    latest: PricePoint
    best: PricePoint

    update_count: int
    movement_percent: float
    implied_probability_change_points: float
    direction: str


@dataclass(frozen=True)
class ClosingLineValue:
    taken_odds: float
    closing_odds: float

    taken_implied_probability: float
    closing_implied_probability: float

    odds_clv_percent: float
    probability_clv_points: float

    beat_close: bool
    verdict: str


def canonical_bookmaker(
    value: str,
) -> str:
    cleaned = " ".join(
        (value or "")
        .strip()
        .lower()
        .split()
    )

    if not cleaned:
        return "Unknown"

    return BOOKMAKER_ALIASES.get(
        cleaned,
        (value or "").strip(),
    )


def calculate_clv(
    *,
    taken_odds: float,
    closing_odds: float,
) -> ClosingLineValue:
    taken = float(taken_odds)
    close = float(closing_odds)

    if taken <= 1.0:
        raise ValueError(
            "Taken decimal odds must be greater than 1.00."
        )

    if close <= 1.0:
        raise ValueError(
            "Closing decimal odds must be greater than 1.00."
        )

    taken_implied = 100.0 / taken
    closing_implied = 100.0 / close

    # Positive when the bettor secured a better price than the close.
    odds_clv = (
        (taken / close) - 1.0
    ) * 100.0

    # Positive when the market later assigned a higher probability
    # to the selection than it did at the price taken.
    probability_clv = (
        closing_implied
        - taken_implied
    )

    beat_close = taken > close

    if odds_clv >= 2.0:
        verdict = "Strong positive CLV"
    elif odds_clv > 0.0:
        verdict = "Positive CLV"
    elif abs(odds_clv) < 0.01:
        verdict = "Matched close"
    elif odds_clv > -2.0:
        verdict = "Negative CLV"
    else:
        verdict = "Weak closing value"

    return ClosingLineValue(
        taken_odds=round(
            taken,
            3,
        ),
        closing_odds=round(
            close,
            3,
        ),
        taken_implied_probability=round(
            taken_implied,
            2,
        ),
        closing_implied_probability=round(
            closing_implied,
            2,
        ),
        odds_clv_percent=round(
            odds_clv,
            2,
        ),
        probability_clv_points=round(
            probability_clv,
            2,
        ),
        beat_close=beat_close,
        verdict=verdict,
    )


def build_price_lifecycle(
    rows: Iterable[OddsSnapshot],
) -> Optional[PriceLifecycle]:
    ordered = sorted(
        list(rows),
        key=lambda row: (
            row.captured_at,
            row.id or 0,
        ),
    )

    if not ordered:
        return None

    first = ordered[0]
    last = ordered[-1]

    opening = PricePoint(
        bookmaker=canonical_bookmaker(
            first.bookmaker
        ),
        decimal_odds=float(
            first.decimal_odds
        ),
        captured_at=first.captured_at,
    )

    latest = PricePoint(
        bookmaker=canonical_bookmaker(
            last.bookmaker
        ),
        decimal_odds=float(
            last.decimal_odds
        ),
        captured_at=last.captured_at,
    )

    best_row = max(
        ordered,
        key=lambda row: (
            float(row.decimal_odds),
            row.captured_at,
        ),
    )

    best = PricePoint(
        bookmaker=canonical_bookmaker(
            best_row.bookmaker
        ),
        decimal_odds=float(
            best_row.decimal_odds
        ),
        captured_at=best_row.captured_at,
    )

    opening_odds = float(
        first.decimal_odds
    )
    latest_odds = float(
        last.decimal_odds
    )

    movement_percent = (
        (
            latest_odds
            / opening_odds
        )
        - 1.0
    ) * 100.0

    opening_implied = (
        100.0
        / opening_odds
    )
    latest_implied = (
        100.0
        / latest_odds
    )

    probability_change = (
        latest_implied
        - opening_implied
    )

    if movement_percent <= -1.0:
        direction = "shortening"
    elif movement_percent >= 1.0:
        direction = "drifting"
    else:
        direction = "stable"

    return PriceLifecycle(
        fixture_date=first.fixture_date,
        tournament=(
            first.tournament
            or "Unknown"
        ),
        player_a=first.player_a,
        player_b=first.player_b,
        market=first.market,
        selection=first.selection,
        opening=opening,
        latest=latest,
        best=best,
        update_count=len(
            ordered
        ),
        movement_percent=round(
            movement_percent,
            2,
        ),
        implied_probability_change_points=round(
            probability_change,
            2,
        ),
        direction=direction,
    )


def market_price_lifecycles(
    rows: Iterable[OddsSnapshot],
) -> list[PriceLifecycle]:
    grouped: dict[
        tuple,
        list[OddsSnapshot],
    ] = {}

    for row in rows:
        key = (
            row.fixture_date,
            row.player_a.casefold(),
            row.player_b.casefold(),
            row.market.casefold(),
            row.selection.casefold(),
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            row
        )

    result = []

    for group in grouped.values():
        lifecycle = (
            build_price_lifecycle(
                group
            )
        )

        if lifecycle is not None:
            result.append(
                lifecycle
            )

    return sorted(
        result,
        key=lambda item: (
            item.fixture_date,
            item.player_a.casefold(),
            item.selection.casefold(),
        ),
    )


def bookmaker_price_lifecycles(
    rows: Iterable[OddsSnapshot],
) -> list[PriceLifecycle]:
    grouped: dict[
        tuple,
        list[OddsSnapshot],
    ] = {}

    for row in rows:
        key = (
            row.fixture_date,
            row.player_a.casefold(),
            row.player_b.casefold(),
            row.market.casefold(),
            row.selection.casefold(),
            canonical_bookmaker(
                row.bookmaker
            ).casefold(),
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            row
        )

    result = []

    for group in grouped.values():
        lifecycle = (
            build_price_lifecycle(
                group
            )
        )

        if lifecycle is not None:
            result.append(
                lifecycle
            )

    return sorted(
        result,
        key=lambda item: (
            item.fixture_date,
            item.player_a.casefold(),
            item.selection.casefold(),
            item.opening.bookmaker.casefold(),
        ),
    )
