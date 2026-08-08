from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.services.bookmaker_quote_ingestion_service import (
    QuoteIngestionReport,
    ingest_bookmaker_payload,
)


@dataclass(frozen=True)
class BookmakerCollectionResult:
    bookmaker_code: str
    success: bool
    quotes_received: int
    snapshots_created: int
    movements_created: int
    unchanged: int
    message: str
    error: Optional[str] = None


@dataclass(frozen=True)
class LiveOddsCollectionReport:
    started_at: datetime
    finished_at: datetime
    bookmaker_results: tuple[
        BookmakerCollectionResult,
        ...,
    ]
    bookmakers_attempted: int
    bookmakers_succeeded: int
    bookmakers_failed: int
    quotes_received: int
    snapshots_created: int
    movements_created: int
    unchanged: int
    success: bool
    message: str


class LiveOddsCollector:
    def __init__(
        self,
        *,
        fetchers: Dict[
            str,
            Callable[[], object],
        ],
    ) -> None:
        self.fetchers = {
            str(code).strip().lower(): fetcher
            for code, fetcher
            in fetchers.items()
        }

    def _collect_one(
        self,
        db: Session,
        *,
        bookmaker_code: str,
        fetcher: Callable[[], object],
    ) -> BookmakerCollectionResult:
        try:
            payload = fetcher()

            report: QuoteIngestionReport = (
                ingest_bookmaker_payload(
                    db,
                    bookmaker_code=bookmaker_code,
                    payload=payload,
                )
            )

            return BookmakerCollectionResult(
                bookmaker_code=bookmaker_code,
                success=True,
                quotes_received=report.quotes_received,
                snapshots_created=report.snapshots_created,
                movements_created=report.movements_created,
                unchanged=report.unchanged,
                message=report.message,
            )

        except Exception as exc:
            return BookmakerCollectionResult(
                bookmaker_code=bookmaker_code,
                success=False,
                quotes_received=0,
                snapshots_created=0,
                movements_created=0,
                unchanged=0,
                message=(
                    f"{bookmaker_code}: collection failed."
                ),
                error=str(exc),
            )

    def collect_once(
        self,
        db: Session,
    ) -> LiveOddsCollectionReport:
        started_at = datetime.utcnow()

        results = []

        for bookmaker_code in sorted(
            self.fetchers.keys()
        ):
            results.append(
                self._collect_one(
                    db,
                    bookmaker_code=bookmaker_code,
                    fetcher=self.fetchers[
                        bookmaker_code
                    ],
                )
            )

        finished_at = datetime.utcnow()

        succeeded = sum(
            item.success
            for item in results
        )

        failed = len(results) - succeeded

        quotes_received = sum(
            item.quotes_received
            for item in results
        )

        snapshots_created = sum(
            item.snapshots_created
            for item in results
        )

        movements_created = sum(
            item.movements_created
            for item in results
        )

        unchanged = sum(
            item.unchanged
            for item in results
        )

        if failed == 0:
            message = (
                "Live odds collection completed successfully."
            )
        elif succeeded > 0:
            message = (
                "Live odds collection completed with partial failures."
            )
        else:
            message = (
                "Live odds collection failed for all bookmakers."
            )

        return LiveOddsCollectionReport(
            started_at=started_at,
            finished_at=finished_at,
            bookmaker_results=tuple(results),
            bookmakers_attempted=len(results),
            bookmakers_succeeded=succeeded,
            bookmakers_failed=failed,
            quotes_received=quotes_received,
            snapshots_created=snapshots_created,
            movements_created=movements_created,
            unchanged=unchanged,
            success=failed == 0,
            message=message,
        )
