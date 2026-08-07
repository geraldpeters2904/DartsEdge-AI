from __future__ import annotations

from datetime import date
from typing import Iterable

from app.db import SessionLocal
from app.models.match import Match
from app.services.fixture_lifecycle_service import (
    CurrentSeriesLifecycleManager,
    FixtureLifecycleRecord,
)
from app.services.sync_checkpoint_service import (
    mark_failure,
    mark_success,
)


CHECKPOINT_NAME = "current-series-lifecycle"


def _records_from_matches(
    matches: Iterable[Match],
) -> list[FixtureLifecycleRecord]:
    return [
        FixtureLifecycleRecord(
            fixture_date=match.date,
            tournament=(
                match.tournament
                or "MODUS"
            ),
            player_a=match.player_a,
            player_b=match.player_b,
            stage=getattr(
                match,
                "stage",
                None,
            ),
            match_format=getattr(
                match,
                "match_format",
                None,
            ),
            status=(
                match.status
                or "scheduled"
            ),
            winner=getattr(
                match,
                "winner",
                None,
            ),
            score_a=getattr(
                match,
                "score_a",
                None,
            ),
            score_b=getattr(
                match,
                "score_b",
                None,
            ),
            provider_id=getattr(
                match,
                "provider_id",
                None,
            ),
        )
        for match in matches
    ]


def build_current_series_fetcher(
    *,
    fetch_matches,
):
    """
    Adapt any current-series MODUS fetch function into the lifecycle
    manager contract.

    fetch_matches(window_start, window_end) must return Match-like
    objects or records with matching attributes.
    """

    def fetch_records(
        window_start: date,
        window_end: date,
    ) -> list[
        FixtureLifecycleRecord
    ]:
        matches = list(
            fetch_matches(
                window_start,
                window_end,
            )
        )

        return _records_from_matches(
            matches
        )

    return fetch_records


def run_current_series_sync_once(
    *,
    fetch_matches,
    past_days: int = 7,
    future_days: int = 7,
    anchor_date: date | None = None,
):
    db = SessionLocal()

    try:
        fetch_records = (
            build_current_series_fetcher(
                fetch_matches=fetch_matches,
            )
        )

        manager = (
            CurrentSeriesLifecycleManager(
                fetch_records=fetch_records,
                past_days=past_days,
                future_days=future_days,
            )
        )

        try:
            report = manager.sync_once(
                db,
                anchor_date=anchor_date,
            )

            mark_success(
                db,
                name=CHECKPOINT_NAME,
                message=report.message,
            )

            return report

        except Exception as exc:
            mark_failure(
                db,
                name=CHECKPOINT_NAME,
                error=str(exc),
            )
            raise

    finally:
        db.close()
