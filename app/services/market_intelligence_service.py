from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.market_snapshot_analysis import (
    MarketSnapshotAnalysis,
)
from app.models.odds_snapshot import OddsSnapshot
from app.services.closing_line_value_service import (
    bookmaker_price_lifecycles,
    calculate_clv,
    canonical_bookmaker,
)


@dataclass(frozen=True)
class MarketAnalysisResult:
    fixture_date: object
    tournament: str
    player_a: str
    player_b: str
    market: str
    selection: str
    bookmaker: str

    opening_odds: float
    latest_odds: float
    best_odds: float
    closing_odds: Optional[float]

    movement_percent: float
    implied_probability_change_points: float
    movement_direction: str
    volatility: str
    update_count: int

    clv_percent: Optional[float]
    probability_clv_points: Optional[float]
    beat_closing_line: Optional[bool]


def _analysis_key(
    *,
    fixture_date,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
    bookmaker: str,
) -> str:
    raw = "|".join([
        fixture_date.isoformat(),
        player_a.strip().casefold(),
        player_b.strip().casefold(),
        market.strip().casefold(),
        selection.strip().casefold(),
        canonical_bookmaker(
            bookmaker
        ).casefold(),
    ])

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def _volatility(
    rows: Iterable[OddsSnapshot],
) -> str:
    prices = [
        float(row.decimal_odds)
        for row in rows
    ]

    if len(prices) < 2:
        return "low"

    mean_price = statistics.fmean(
        prices
    )

    if mean_price <= 0:
        return "low"

    standard_deviation = (
        statistics.pstdev(
            prices
        )
    )

    coefficient = (
        standard_deviation
        / mean_price
    )

    if coefficient >= 0.08:
        return "extreme"

    if coefficient >= 0.04:
        return "high"

    if coefficient >= 0.015:
        return "medium"

    return "low"


def analyse_bookmaker_market(
    rows: Iterable[OddsSnapshot],
    *,
    closing_odds: Optional[float] = None,
) -> Optional[MarketAnalysisResult]:
    rows = list(
        rows
    )

    if not rows:
        return None

    lifecycle_rows = (
        bookmaker_price_lifecycles(
            rows
        )
    )

    if len(
        lifecycle_rows
    ) != 1:
        raise ValueError(
            "analyse_bookmaker_market requires one fixture, market, "
            "selection and bookmaker group."
        )

    lifecycle = (
        lifecycle_rows[0]
    )

    clv = None

    if closing_odds is not None:
        clv = calculate_clv(
            taken_odds=(
                lifecycle.latest
                .decimal_odds
            ),
            closing_odds=float(
                closing_odds
            ),
        )

    return MarketAnalysisResult(
        fixture_date=(
            lifecycle.fixture_date
        ),
        tournament=(
            lifecycle.tournament
        ),
        player_a=(
            lifecycle.player_a
        ),
        player_b=(
            lifecycle.player_b
        ),
        market=(
            lifecycle.market
        ),
        selection=(
            lifecycle.selection
        ),
        bookmaker=(
            lifecycle.opening
            .bookmaker
        ),
        opening_odds=round(
            lifecycle.opening
            .decimal_odds,
            3,
        ),
        latest_odds=round(
            lifecycle.latest
            .decimal_odds,
            3,
        ),
        best_odds=round(
            lifecycle.best
            .decimal_odds,
            3,
        ),
        closing_odds=(
            round(
                float(
                    closing_odds
                ),
                3,
            )
            if closing_odds
            is not None
            else None
        ),
        movement_percent=(
            lifecycle
            .movement_percent
        ),
        implied_probability_change_points=(
            lifecycle
            .implied_probability_change_points
        ),
        movement_direction=(
            lifecycle.direction
        ),
        volatility=(
            _volatility(
                rows
            )
        ),
        update_count=(
            lifecycle.update_count
        ),
        clv_percent=(
            clv.odds_clv_percent
            if clv
            else None
        ),
        probability_clv_points=(
            clv.probability_clv_points
            if clv
            else None
        ),
        beat_closing_line=(
            clv.beat_close
            if clv
            else None
        ),
    )


def upsert_market_analysis(
    db: Session,
    result: MarketAnalysisResult,
) -> tuple[
    MarketSnapshotAnalysis,
    bool,
]:
    key = _analysis_key(
        fixture_date=(
            result.fixture_date
        ),
        player_a=(
            result.player_a
        ),
        player_b=(
            result.player_b
        ),
        market=(
            result.market
        ),
        selection=(
            result.selection
        ),
        bookmaker=(
            result.bookmaker
        ),
    )

    row = (
        db.query(
            MarketSnapshotAnalysis
        )
        .filter(
            MarketSnapshotAnalysis
            .analysis_key
            == key
        )
        .first()
    )

    created = (
        row is None
    )

    if row is None:
        row = (
            MarketSnapshotAnalysis(
                analysis_key=key,
                fixture_date=(
                    result.fixture_date
                ),
                tournament=(
                    result.tournament
                ),
                player_a=(
                    result.player_a
                ),
                player_b=(
                    result.player_b
                ),
                market=(
                    result.market
                ),
                selection=(
                    result.selection
                ),
                bookmaker=(
                    canonical_bookmaker(
                        result.bookmaker
                    )
                ),
                opening_odds=(
                    result.opening_odds
                ),
                latest_odds=(
                    result.latest_odds
                ),
                best_odds=(
                    result.best_odds
                ),
                closing_odds=(
                    result.closing_odds
                ),
                movement_percent=(
                    result
                    .movement_percent
                ),
                implied_probability_change_points=(
                    result
                    .implied_probability_change_points
                ),
                movement_direction=(
                    result
                    .movement_direction
                ),
                volatility=(
                    result.volatility
                ),
                update_count=(
                    result.update_count
                ),
                clv_percent=(
                    result.clv_percent
                ),
                probability_clv_points=(
                    result
                    .probability_clv_points
                ),
                beat_closing_line=(
                    (
                        1
                        if result
                        .beat_closing_line
                        else 0
                    )
                    if result
                    .beat_closing_line
                    is not None
                    else None
                ),
                analysed_at=(
                    datetime.utcnow()
                ),
            )
        )

        db.add(
            row
        )

    else:
        # Opening price is intentionally immutable.
        row.latest_odds = (
            result.latest_odds
        )
        row.best_odds = max(
            float(
                row.best_odds
            ),
            float(
                result.best_odds
            ),
        )
        row.closing_odds = (
            result.closing_odds
        )
        row.movement_percent = (
            result
            .movement_percent
        )
        row.implied_probability_change_points = (
            result
            .implied_probability_change_points
        )
        row.movement_direction = (
            result
            .movement_direction
        )
        row.volatility = (
            result.volatility
        )
        row.update_count = (
            result.update_count
        )
        row.clv_percent = (
            result.clv_percent
        )
        row.probability_clv_points = (
            result
            .probability_clv_points
        )
        row.beat_closing_line = (
            (
                1
                if result
                .beat_closing_line
                else 0
            )
            if result
            .beat_closing_line
            is not None
            else None
        )
        row.analysed_at = (
            datetime.utcnow()
        )

    db.commit()
    db.refresh(
        row
    )

    return (
        row,
        created,
    )


def rebuild_market_analyses(
    db: Session,
    *,
    snapshots: Optional[
        Iterable[OddsSnapshot]
    ] = None,
) -> dict:
    rows = (
        list(
            snapshots
        )
        if snapshots
        is not None
        else (
            db.query(
                OddsSnapshot
            )
            .order_by(
                OddsSnapshot
                .captured_at
                .asc()
            )
            .all()
        )
    )

    groups: dict[
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

        groups.setdefault(
            key,
            [],
        ).append(
            row
        )

    created = 0
    updated = 0
    skipped = 0

    for group in groups.values():
        try:
            result = (
                analyse_bookmaker_market(
                    group
                )
            )

            if result is None:
                skipped += 1
                continue

            _, was_created = (
                upsert_market_analysis(
                    db,
                    result,
                )
            )

            if was_created:
                created += 1
            else:
                updated += 1

        except Exception:
            skipped += 1

    return {
        "groups": len(
            groups
        ),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def bookmaker_scorecards(
    db: Session,
) -> list[dict]:
    rows = (
        db.query(
            MarketSnapshotAnalysis
        )
        .all()
    )

    grouped: dict[
        str,
        list[
            MarketSnapshotAnalysis
        ],
    ] = {}

    for row in rows:
        grouped.setdefault(
            canonical_bookmaker(
                row.bookmaker
            ),
            [],
        ).append(
            row
        )

    scorecards = []

    for bookmaker, items in grouped.items():
        clv_rows = [
            item
            for item in items
            if item.clv_percent
            is not None
        ]

        scorecards.append({
            "bookmaker": bookmaker,
            "markets": len(
                items
            ),
            "average_movement_percent": (
                round(
                    statistics.fmean(
                        float(
                            item
                            .movement_percent
                        )
                        for item
                        in items
                    ),
                    2,
                )
                if items
                else None
            ),
            "average_clv_percent": (
                round(
                    statistics.fmean(
                        float(
                            item
                            .clv_percent
                        )
                        for item
                        in clv_rows
                    ),
                    2,
                )
                if clv_rows
                else None
            ),
            "beat_close_percent": (
                round(
                    sum(
                        int(
                            item
                            .beat_closing_line
                            == 1
                        )
                        for item
                        in clv_rows
                    )
                    / len(
                        clv_rows
                    )
                    * 100.0,
                    1,
                )
                if clv_rows
                else None
            ),
        })

    return sorted(
        scorecards,
        key=lambda row: (
            -row["markets"],
            row["bookmaker"],
        ),
    )
