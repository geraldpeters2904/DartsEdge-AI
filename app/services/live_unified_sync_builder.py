from __future__ import annotations

from app.services.current_series_modus_adapter import (
    run_current_series_sync_once,
)
from app.services.current_series_modus_fetcher import (
    fetch_current_modus_matches,
)
from app.services.settlement_sync_adapter import (
    run_settlement_sync_once,
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
    )
