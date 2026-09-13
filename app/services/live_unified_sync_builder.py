from __future__ import annotations

from datetime import datetime

from app.services.current_series_modus_adapter import (
    run_current_series_sync_once,
)
from app.services.current_series_modus_fetcher import (
    fetch_current_modus_matches,
)
from app.services.settlement_sync_adapter import (
    run_settlement_sync_once,
)
from app.services.bookmaker_capture_types import (
    BookmakerCaptureReport,
)
from app.services.paddy_power_live_capture import (
    PADDY_POWER_MODUS_URL,
    build_paddy_power_capture_once,
    capture_paddy_power_discovered_events_report_once,
)
from app.services.unified_sync_manager_service import (
    UnifiedSynchronisationManager,
)


def build_live_unified_manager(
    *,
    bookmaker_capture=None,
    historical_backfill=None,
    poll_seconds: float = 180.0,
    historical_every_n_cycles: int = 5,
):
    shutdown_callback = None

    def current_series():
        return (
            run_current_series_sync_once(
                fetch_matches=(
                    fetch_current_modus_matches
                ),
                past_days=7,
                future_days=7,
            )
        )

    if bookmaker_capture is None:

        def bookmaker_capture():

            from app.db import SessionLocal

            capture_once, capture_service = (

                build_paddy_power_capture_once()

            )

            db = SessionLocal()

            try:

                try:
                    category_report = capture_once(db)
                except TimeoutError:
                    return BookmakerCaptureReport(
                        bookmaker="Paddy Power",
                        source_url=PADDY_POWER_MODUS_URL,
                        captured_at=datetime.utcnow(),
                        extracted_prices=0,
                        stored_prices=0,
                        unchanged_prices=0,
                        skipped_prices=0,
                        challenge_detected=False,
                        message=(
                            "Paddy Power MODUS markets are "
                            "not currently published."
                        ),
                    )

                category_html = (
                    capture_service.browser_session.html()
                )

                event_report = (
                    capture_paddy_power_discovered_events_report_once(
                        db,
                        category_html=category_html,
                        service=capture_service,
                    )
                )

                return BookmakerCaptureReport(
                    bookmaker="Paddy Power",
                    source_url=(
                        category_report.source_url
                    ),
                    captured_at=max(
                        category_report.captured_at,
                        event_report.captured_at,
                    ),
                    extracted_prices=(
                        category_report.extracted_prices
                        + event_report.extracted_prices
                    ),
                    stored_prices=(
                        category_report.stored_prices
                        + event_report.stored_prices
                    ),
                    unchanged_prices=(
                        category_report.unchanged_prices
                        + event_report.unchanged_prices
                    ),
                    skipped_prices=(
                        category_report.skipped_prices
                        + event_report.skipped_prices
                    ),
                    challenge_detected=(
                        category_report.challenge_detected
                        or event_report.challenge_detected
                    ),
                    message=(
                        "Paddy Power category and event "
                        "capture completed."
                    ),
                )

            finally:

                db.close()

                capture_service.close()

    return UnifiedSynchronisationManager(
        current_series_sync=current_series,
        settlement_sync=(
            run_settlement_sync_once
        ),
        bookmaker_capture=(
            bookmaker_capture
        ),
        historical_backfill=(
            historical_backfill
        ),
        poll_seconds=poll_seconds,
        historical_every_n_cycles=(
            historical_every_n_cycles
        ),
        shutdown_callback=shutdown_callback,
    )
