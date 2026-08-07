from datetime import date

from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.odds_snapshot import OddsSnapshot
from app.services.closing_line_value_service import canonical_bookmaker
from app.services.market_consensus_service import (
    analyse_market_consensus,
    consensus_summary,
)
from app.services.odds_warehouse_service import bookmaker_coverage
from app.templates_config import templates

router = APIRouter()


def _latest_market_rows(db, *, limit: int = 100):
    rows = (
        db.query(OddsSnapshot)
        .order_by(
            OddsSnapshot.fixture_date.desc(),
            OddsSnapshot.captured_at.desc(),
            OddsSnapshot.id.desc(),
        )
        .limit(max(1, min(int(limit), 1000)))
        .all()
    )

    grouped = {}

    for row in rows:
        key = (
            row.fixture_date,
            row.player_a.casefold(),
            row.player_b.casefold(),
            row.market.casefold(),
            row.selection.casefold(),
        )

        item = grouped.setdefault(
            key,
            {
                "fixture_date": row.fixture_date,
                "tournament": row.tournament or "Unknown",
                "player_a": row.player_a,
                "player_b": row.player_b,
                "market": row.market,
                "selection": row.selection,
                "rows": [],
                "prices": {},
                "snapshot_count": 0,
            },
        )

        item["rows"].append(row)
        item["snapshot_count"] += 1

        bookmaker = canonical_bookmaker(row.bookmaker)
        current = item["prices"].get(bookmaker)

        if (
            current is None
            or row.captured_at > current.captured_at
            or (
                row.captured_at == current.captured_at
                and (row.id or 0) > (current.id or 0)
            )
        ):
            item["prices"][bookmaker] = row

    result = []

    for item in grouped.values():
        latest_prices = list(item["prices"].values())

        best = (
            max(
                latest_prices,
                key=lambda row: float(row.decimal_odds),
            )
            if latest_prices
            else None
        )

        paddy = item["prices"].get("Paddy Power")
        bet365 = item["prices"].get("Bet365")

        consensus = consensus_summary(
            analyse_market_consensus(
                item["rows"]
            )
        )

        result.append(
            {
                "fixture_date": item["fixture_date"],
                "tournament": item["tournament"],
                "player_a": item["player_a"],
                "player_b": item["player_b"],
                "market": item["market"],
                "selection": item["selection"],
                "snapshot_count": item["snapshot_count"],
                "bookmaker_count": len(item["prices"]),
                "best_bookmaker": (
                    canonical_bookmaker(best.bookmaker)
                    if best
                    else None
                ),
                "best_odds": (
                    float(best.decimal_odds)
                    if best
                    else None
                ),
                "paddy_power_odds": (
                    float(paddy.decimal_odds)
                    if paddy
                    else None
                ),
                "bet365_odds": (
                    float(bet365.decimal_odds)
                    if bet365
                    else None
                ),
                "consensus": consensus,
            }
        )

    result.sort(
        key=lambda row: (
            row["fixture_date"],
            (
                row["consensus"]["consensus_score"]
                if row["consensus"]
                else -1
            ),
            row["best_odds"] or 0.0,
        ),
        reverse=True,
    )

    return result


@router.get("/odds-warehouse")
def odds_warehouse_page(request: Request):
    db = SessionLocal()

    try:
        rows = _latest_market_rows(
            db,
            limit=500,
        )

        coverage = bookmaker_coverage(db)

        priority_coverage = [
            row
            for row in coverage
            if row["priority"]
        ]

        coordinated_count = sum(
            1
            for row in rows
            if (
                row["consensus"]
                and row["consensus"]["coordinated_move"]
            )
        )

        strong_consensus_count = sum(
            1
            for row in rows
            if (
                row["consensus"]
                and row["consensus"]["consensus_score"] >= 75
            )
        )

        outlier_market_count = sum(
            1
            for row in rows
            if (
                row["consensus"]
                and row["consensus"]["outlier_bookmakers"]
            )
        )

        return templates.TemplateResponse(
            "odds_warehouse.html",
            {
                "request": request,
                "today": date.today(),
                "markets": rows,
                "coverage": coverage,
                "priority_coverage": priority_coverage,
                "market_count": len(rows),
                "bookmaker_count": len(coverage),
                "snapshot_count": sum(
                    row["snapshots"]
                    for row in coverage
                ),
                "coordinated_count": coordinated_count,
                "strong_consensus_count": strong_consensus_count,
                "outlier_market_count": outlier_market_count,
            },
        )
    finally:
        db.close()
