from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.market_snapshot_analysis import (
    MarketSnapshotAnalysis,
)
from app.models.odds_snapshot import OddsSnapshot
from app.services.closing_line_value_service import (
    canonical_bookmaker,
)


PRIMARY_BOOKMAKERS = (
    "Paddy Power",
    "Bet365",
)


@dataclass(frozen=True)
class OddsWarehousePrice:
    bookmaker: str
    decimal_odds: float
    captured_at: object
    provider_id: Optional[str]


@dataclass(frozen=True)
class OddsWarehouseMarket:
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    market: str
    selection: str

    best_price: Optional[OddsWarehousePrice]
    paddy_power: Optional[OddsWarehousePrice]
    bet365: Optional[OddsWarehousePrice]

    bookmaker_count: int
    snapshot_count: int

    opening_odds: Optional[float]
    latest_odds: Optional[float]
    movement_percent: Optional[float]
    movement_direction: Optional[str]
    volatility: Optional[str]

    closing_odds: Optional[float]
    clv_percent: Optional[float]


def _normalise(
    value: str | None,
) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _same_fixture(
    row,
    *,
    fixture_date: date,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
) -> bool:
    return (
        row.fixture_date == fixture_date
        and _normalise(row.player_a) == _normalise(player_a)
        and _normalise(row.player_b) == _normalise(player_b)
        and _normalise(row.market) == _normalise(market)
        and _normalise(row.selection) == _normalise(selection)
    )


def _latest_by_bookmaker(
    rows: Iterable[OddsSnapshot],
) -> dict[str, OddsSnapshot]:
    latest: dict[str, OddsSnapshot] = {}

    for row in rows:
        bookmaker = canonical_bookmaker(
            row.bookmaker
        )

        current = latest.get(
            bookmaker
        )

        if (
            current is None
            or row.captured_at > current.captured_at
            or (
                row.captured_at == current.captured_at
                and (row.id or 0) > (current.id or 0)
            )
        ):
            latest[bookmaker] = row

    return latest


def _price(
    row: Optional[OddsSnapshot],
) -> Optional[OddsWarehousePrice]:
    if row is None:
        return None

    return OddsWarehousePrice(
        bookmaker=canonical_bookmaker(
            row.bookmaker
        ),
        decimal_odds=round(
            float(
                row.decimal_odds
            ),
            3,
        ),
        captured_at=row.captured_at,
        provider_id=(
            getattr(
                row,
                "provider_id",
                None,
            )
        ),
    )


def _analysis_for_bookmaker(
    rows: Iterable[MarketSnapshotAnalysis],
    bookmaker: str,
) -> Optional[MarketSnapshotAnalysis]:
    bookmaker = canonical_bookmaker(
        bookmaker
    )

    candidates = [
        row
        for row in rows
        if canonical_bookmaker(
            row.bookmaker
        ) == bookmaker
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda row: (
            row.analysed_at,
            row.id or 0,
        ),
    )


def build_market_view(
    *,
    snapshots: Iterable[OddsSnapshot],
    analyses: Iterable[MarketSnapshotAnalysis] = (),
) -> Optional[OddsWarehouseMarket]:
    snapshots = list(
        snapshots
    )

    if not snapshots:
        return None

    analyses = list(
        analyses
    )

    first = min(
        snapshots,
        key=lambda row: (
            row.captured_at,
            row.id or 0,
        ),
    )

    latest_by_bookmaker = (
        _latest_by_bookmaker(
            snapshots
        )
    )

    latest_prices = list(
        latest_by_bookmaker.values()
    )

    best_row = (
        max(
            latest_prices,
            key=lambda row: (
                float(
                    row.decimal_odds
                ),
                row.captured_at,
            ),
        )
        if latest_prices
        else None
    )

    paddy = latest_by_bookmaker.get(
        "Paddy Power"
    )

    bet365 = latest_by_bookmaker.get(
        "Bet365"
    )

    preferred_analysis = (
        _analysis_for_bookmaker(
            analyses,
            "Paddy Power",
        )
        or _analysis_for_bookmaker(
            analyses,
            "Bet365",
        )
        or (
            max(
                analyses,
                key=lambda row: (
                    row.analysed_at,
                    row.id or 0,
                ),
            )
            if analyses
            else None
        )
    )

    return OddsWarehouseMarket(
        fixture_date=first.fixture_date,
        tournament=(
            first.tournament
            or "Unknown"
        ),
        player_a=first.player_a,
        player_b=first.player_b,
        market=first.market,
        selection=first.selection,
        best_price=_price(
            best_row
        ),
        paddy_power=_price(
            paddy
        ),
        bet365=_price(
            bet365
        ),
        bookmaker_count=len(
            latest_by_bookmaker
        ),
        snapshot_count=len(
            snapshots
        ),
        opening_odds=(
            round(
                float(
                    preferred_analysis
                    .opening_odds
                ),
                3,
            )
            if preferred_analysis
            is not None
            else round(
                float(
                    first.decimal_odds
                ),
                3,
            )
        ),
        latest_odds=(
            round(
                float(
                    preferred_analysis
                    .latest_odds
                ),
                3,
            )
            if preferred_analysis
            is not None
            else (
                round(
                    float(
                        best_row
                        .decimal_odds
                    ),
                    3,
                )
                if best_row
                is not None
                else None
            )
        ),
        movement_percent=(
            float(
                preferred_analysis
                .movement_percent
            )
            if preferred_analysis
            is not None
            else None
        ),
        movement_direction=(
            preferred_analysis
            .movement_direction
            if preferred_analysis
            is not None
            else None
        ),
        volatility=(
            preferred_analysis
            .volatility
            if preferred_analysis
            is not None
            else None
        ),
        closing_odds=(
            float(
                preferred_analysis
                .closing_odds
            )
            if (
                preferred_analysis
                is not None
                and preferred_analysis
                .closing_odds
                is not None
            )
            else None
        ),
        clv_percent=(
            float(
                preferred_analysis
                .clv_percent
            )
            if (
                preferred_analysis
                is not None
                and preferred_analysis
                .clv_percent
                is not None
            )
            else None
        ),
    )


def market_view(
    db: Session,
    *,
    fixture_date: date,
    player_a: str,
    player_b: str,
    market: str = "match_winner",
    selection: str,
) -> Optional[OddsWarehouseMarket]:
    snapshots = (
        db.query(
            OddsSnapshot
        )
        .filter(
            OddsSnapshot.fixture_date
            == fixture_date
        )
        .order_by(
            OddsSnapshot
            .captured_at
            .asc()
        )
        .all()
    )

    snapshots = [
        row
        for row
        in snapshots
        if _same_fixture(
            row,
            fixture_date=(
                fixture_date
            ),
            player_a=player_a,
            player_b=player_b,
            market=market,
            selection=selection,
        )
    ]

    if not snapshots:
        return None

    analyses = (
        db.query(
            MarketSnapshotAnalysis
        )
        .filter(
            MarketSnapshotAnalysis
            .fixture_date
            == fixture_date
        )
        .all()
    )

    analyses = [
        row
        for row
        in analyses
        if _same_fixture(
            row,
            fixture_date=(
                fixture_date
            ),
            player_a=player_a,
            player_b=player_b,
            market=market,
            selection=selection,
        )
    ]

    return build_market_view(
        snapshots=snapshots,
        analyses=analyses,
    )


def bookmaker_coverage(
    db: Session,
    *,
    fixture_date_from: Optional[
        date
    ] = None,
    fixture_date_to: Optional[
        date
    ] = None,
) -> list[dict]:
    query = db.query(
        OddsSnapshot
    )

    if fixture_date_from is not None:
        query = query.filter(
            OddsSnapshot.fixture_date
            >= fixture_date_from
        )

    if fixture_date_to is not None:
        query = query.filter(
            OddsSnapshot.fixture_date
            <= fixture_date_to
        )

    rows = query.all()

    grouped: dict[
        str,
        dict,
    ] = {}

    for row in rows:
        bookmaker = (
            canonical_bookmaker(
                row.bookmaker
            )
        )

        item = grouped.setdefault(
            bookmaker,
            {
                "bookmaker": bookmaker,
                "snapshots": 0,
                "fixtures": set(),
                "markets": set(),
                "selections": set(),
            },
        )

        item[
            "snapshots"
        ] += 1

        item[
            "fixtures"
        ].add((
            row.fixture_date,
            _normalise(
                row.player_a
            ),
            _normalise(
                row.player_b
            ),
        ))

        item[
            "markets"
        ].add(
            _normalise(
                row.market
            )
        )

        item[
            "selections"
        ].add((
            row.fixture_date,
            _normalise(
                row.player_a
            ),
            _normalise(
                row.player_b
            ),
            _normalise(
                row.market
            ),
            _normalise(
                row.selection
            ),
        ))

    result = []

    for bookmaker, item in grouped.items():
        result.append({
            "bookmaker": bookmaker,
            "priority": (
                bookmaker
                in PRIMARY_BOOKMAKERS
            ),
            "snapshots": (
                item[
                    "snapshots"
                ]
            ),
            "fixtures": len(
                item[
                    "fixtures"
                ]
            ),
            "markets": len(
                item[
                    "markets"
                ]
            ),
            "selections": len(
                item[
                    "selections"
                ]
            ),
        })

    return sorted(
        result,
        key=lambda row: (
            0
            if row[
                "priority"
            ]
            else 1,
            -row[
                "snapshots"
            ],
            row[
                "bookmaker"
            ],
        ),
    )
