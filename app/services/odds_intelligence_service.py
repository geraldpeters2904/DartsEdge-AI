from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from statistics import mean
from typing import Iterable, Optional, Sequence

from app.models.odds_snapshot import OddsSnapshot
from app.services.player_name_service import (
    normalise_player_name,
)


@dataclass(frozen=True)
class OddsMovementPoint:
    bookmaker: str
    decimal_odds: float
    implied_probability: float
    captured_at: datetime


@dataclass(frozen=True)
class OddsIntelligence:
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    market: str
    selection: str

    opening_price: float
    latest_price: float
    best_price: float
    worst_price: float

    opening_bookmaker: str
    latest_bookmaker: str
    best_bookmaker: str

    opening_implied_probability: float
    latest_implied_probability: float

    price_change: float
    price_change_percent: float
    implied_probability_change: float

    update_count: int
    bookmaker_count: int

    average_price: float
    price_standard_deviation: float

    market_direction: str
    volatility: str
    steam_move: bool
    drift_move: bool

    first_captured_at: datetime
    latest_captured_at: datetime
    elapsed_minutes: float

    history: tuple[OddsMovementPoint, ...]


def _normalise(value: str | None) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .casefold()
        .split()
    )


def _fixture_players_match(
    row: OddsSnapshot,
    player_a: str,
    player_b: str,
) -> bool:
    expected = {
        normalise_player_name(player_a),
        normalise_player_name(player_b),
    }

    actual = {
        normalise_player_name(row.player_a),
        normalise_player_name(row.player_b),
    }

    return actual == expected


def _population_standard_deviation(
    values: Sequence[float],
) -> float:
    if not values:
        return 0.0

    average = mean(values)

    variance = mean(
        (value - average) ** 2
        for value in values
    )

    return sqrt(variance)


def _market_direction(
    opening_price: float,
    latest_price: float,
    *,
    stable_threshold_percent: float,
) -> str:
    if opening_price <= 0:
        return "unknown"

    movement_percent = (
        (latest_price - opening_price)
        / opening_price
        * 100.0
    )

    if abs(movement_percent) <= stable_threshold_percent:
        return "stable"

    if latest_price < opening_price:
        return "shortening"

    return "drifting"


def _volatility_label(
    prices: Sequence[float],
) -> str:
    if len(prices) < 2:
        return "none"

    average = mean(prices)

    if average <= 0:
        return "none"

    coefficient = (
        _population_standard_deviation(prices)
        / average
        * 100.0
    )

    if coefficient < 1.0:
        return "low"

    if coefficient < 3.0:
        return "medium"

    return "high"


def analyse_snapshots(
    rows: Iterable[OddsSnapshot],
    *,
    stable_threshold_percent: float = 0.5,
    steam_threshold_percent: float = 5.0,
    steam_window_minutes: float = 60.0,
) -> Optional[OddsIntelligence]:
    ordered = sorted(
        tuple(rows),
        key=lambda row: (
            row.captured_at,
            row.id or 0,
        ),
    )

    if not ordered:
        return None

    opening = ordered[0]
    latest = ordered[-1]

    best = max(
        ordered,
        key=lambda row: (
            float(row.decimal_odds),
            row.captured_at,
        ),
    )

    worst = min(
        ordered,
        key=lambda row: (
            float(row.decimal_odds),
            row.captured_at,
        ),
    )

    opening_price = float(
        opening.decimal_odds
    )
    latest_price = float(
        latest.decimal_odds
    )

    prices = [
        float(row.decimal_odds)
        for row in ordered
    ]

    price_change = (
        latest_price
        - opening_price
    )

    price_change_percent = (
        price_change
        / opening_price
        * 100.0
        if opening_price > 0
        else 0.0
    )

    opening_implied = (
        100.0
        / opening_price
    )

    latest_implied = (
        100.0
        / latest_price
    )

    implied_change = (
        latest_implied
        - opening_implied
    )

    elapsed_minutes = max(
        (
            latest.captured_at
            - opening.captured_at
        ).total_seconds()
        / 60.0,
        0.0,
    )

    direction = _market_direction(
        opening_price,
        latest_price,
        stable_threshold_percent=(
            stable_threshold_percent
        ),
    )

    movement_size = abs(
        price_change_percent
    )

    steam_move = (
        direction == "shortening"
        and movement_size
        >= steam_threshold_percent
        and elapsed_minutes
        <= steam_window_minutes
    )

    drift_move = (
        direction == "drifting"
        and movement_size
        >= steam_threshold_percent
        and elapsed_minutes
        <= steam_window_minutes
    )

    history = tuple(
        OddsMovementPoint(
            bookmaker=row.bookmaker,
            decimal_odds=round(
                float(row.decimal_odds),
                3,
            ),
            implied_probability=round(
                100.0
                / float(row.decimal_odds),
                3,
            ),
            captured_at=row.captured_at,
        )
        for row in ordered
    )

    return OddsIntelligence(
        fixture_date=opening.fixture_date,
        tournament=(
            opening.tournament
            or "Unknown"
        ),
        player_a=opening.player_a,
        player_b=opening.player_b,
        market=opening.market,
        selection=opening.selection,

        opening_price=round(
            opening_price,
            3,
        ),
        latest_price=round(
            latest_price,
            3,
        ),
        best_price=round(
            float(best.decimal_odds),
            3,
        ),
        worst_price=round(
            float(worst.decimal_odds),
            3,
        ),

        opening_bookmaker=opening.bookmaker,
        latest_bookmaker=latest.bookmaker,
        best_bookmaker=best.bookmaker,

        opening_implied_probability=round(
            opening_implied,
            3,
        ),
        latest_implied_probability=round(
            latest_implied,
            3,
        ),

        price_change=round(
            price_change,
            3,
        ),
        price_change_percent=round(
            price_change_percent,
            3,
        ),
        implied_probability_change=round(
            implied_change,
            3,
        ),

        update_count=len(ordered),
        bookmaker_count=len({
            _normalise(row.bookmaker)
            for row in ordered
        }),

        average_price=round(
            mean(prices),
            3,
        ),
        price_standard_deviation=round(
            _population_standard_deviation(
                prices
            ),
            4,
        ),

        market_direction=direction,
        volatility=_volatility_label(
            prices
        ),
        steam_move=steam_move,
        drift_move=drift_move,

        first_captured_at=(
            opening.captured_at
        ),
        latest_captured_at=(
            latest.captured_at
        ),
        elapsed_minutes=round(
            elapsed_minutes,
            2,
        ),

        history=history,
    )


def market_snapshots(
    db,
    *,
    fixture_date: date,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
    tournament: Optional[str] = None,
) -> list[OddsSnapshot]:
    query = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_date
            == fixture_date,
            OddsSnapshot.market
            == market,
            OddsSnapshot.selection
            == selection,
        )
        .order_by(
            OddsSnapshot.captured_at.asc(),
            OddsSnapshot.id.asc(),
        )
    )

    rows = query.all()

    expected_tournament = (
        _normalise(tournament)
        if tournament
        else None
    )

    return [
        row
        for row in rows
        if _fixture_players_match(
            row,
            player_a,
            player_b,
        )
        and (
            expected_tournament is None
            or _normalise(
                row.tournament
            )
            == expected_tournament
        )
    ]


def analyse_market(
    db,
    *,
    fixture_date: date,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
    tournament: Optional[str] = None,
    stable_threshold_percent: float = 0.5,
    steam_threshold_percent: float = 5.0,
    steam_window_minutes: float = 60.0,
) -> Optional[OddsIntelligence]:
    rows = market_snapshots(
        db,
        fixture_date=fixture_date,
        player_a=player_a,
        player_b=player_b,
        market=market,
        selection=selection,
        tournament=tournament,
    )

    return analyse_snapshots(
        rows,
        stable_threshold_percent=(
            stable_threshold_percent
        ),
        steam_threshold_percent=(
            steam_threshold_percent
        ),
        steam_window_minutes=(
            steam_window_minutes
        ),
    )


def closing_line_value_percent(
    taken_odds: float,
    closing_odds: float,
) -> float:
    taken = float(taken_odds)
    closing = float(closing_odds)

    if taken <= 1.0:
        raise ValueError(
            "Taken odds must be greater than 1.00."
        )

    if closing <= 1.0:
        raise ValueError(
            "Closing odds must be greater than 1.00."
        )

    return round(
        (
            taken
            / closing
            - 1.0
        )
        * 100.0,
        3,
    )
