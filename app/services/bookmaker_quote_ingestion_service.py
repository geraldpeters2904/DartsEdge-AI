from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.bookmaker_adapter_registry import (
    BookmakerAdapterRegistry,
    default_bookmaker_registry,
)
from app.services.odds_warehouse_foundation_service import (
    ensure_bookmaker,
    record_odds,
)


@dataclass(frozen=True)
class QuoteIngestionReport:
    bookmaker_code: str
    quotes_received: int
    snapshots_created: int
    movements_created: int
    unchanged: int
    message: str


def ingest_bookmaker_payload(
    db: Session,
    *,
    bookmaker_code: str,
    payload,
    registry: BookmakerAdapterRegistry = None,
) -> QuoteIngestionReport:
    registry = (
        registry
        or default_bookmaker_registry()
    )

    adapter = registry.get(
        bookmaker_code
    )

    ensure_bookmaker(
        db,
        code=adapter.bookmaker_code,
        name=adapter.bookmaker_name,
        priority=(
            10
            if adapter.bookmaker_code
            == "paddypower"
            else 20
        ),
    )

    extraction = (
        adapter.extract_quotes(
            payload
        )
    )

    snapshots_created = 0
    movements_created = 0
    unchanged = 0

    for quote in extraction.quotes:
        result = record_odds(
            db,
            fixture_id=(
                quote.fixture_id
            ),
            bookmaker_code=(
                quote.bookmaker_code
            ),
            market=quote.market,
            selection=quote.selection,
            decimal_odds=(
                quote.decimal_odds
            ),
            captured_at=(
                quote.captured_at
            ),
            source_reference=(
                quote.source_reference
            ),
        )

        if result.snapshot_created:
            snapshots_created += 1
        else:
            unchanged += 1

        if result.movement_created:
            movements_created += 1

    return QuoteIngestionReport(
        bookmaker_code=(
            adapter.bookmaker_code
        ),
        quotes_received=(
            extraction.quote_count
        ),
        snapshots_created=(
            snapshots_created
        ),
        movements_created=(
            movements_created
        ),
        unchanged=unchanged,
        message=(
            f"{adapter.bookmaker_name}: "
            f"{snapshots_created} snapshot(s), "
            f"{movements_created} movement(s), "
            f"{unchanged} unchanged."
        ),
    )
