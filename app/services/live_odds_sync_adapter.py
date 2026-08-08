from __future__ import annotations

from app.db import SessionLocal
from app.services.live_bookmaker_fetchers import (
    fetch_bet365_quotes,
    fetch_paddy_power_quotes,
)
from app.services.live_odds_collector_service import (
    LiveOddsCollector,
)
from app.services.sync_checkpoint_service import (
    mark_failure,
    mark_success,
)


CHECKPOINT_NAME = "live-odds-collector"


def build_live_odds_collector(
) -> LiveOddsCollector:
    return LiveOddsCollector(
        fetchers={
            "paddypower": fetch_paddy_power_quotes,
            "bet365": fetch_bet365_quotes,
        }
    )


def run_live_odds_collection_once():
    db = SessionLocal()

    try:
        collector = build_live_odds_collector()

        try:
            report = collector.collect_once(
                db
            )

            if report.bookmakers_failed:
                mark_failure(
                    db,
                    name=CHECKPOINT_NAME,
                    error=report.message,
                )
            else:
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
