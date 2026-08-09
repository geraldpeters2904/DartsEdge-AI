from __future__ import annotations

from datetime import date

from app.db import SessionLocal
from app.models.match import Match
from app.services.bookmaker_capture_manager_service import (
    BookmakerCaptureManager,
)
from app.services.paddy_power_capture_service import (
    PaddyPowerCaptureService,
)
from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
    PaddyPowerModusExtractor,
)


PADDY_POWER_MODUS_URL = (
    "https://www.paddypower.com/darts/"
    "modus-super-series"
)


def _scheduled_modus_fixtures(
    db,
):
    today = date.today()

    rows = (
        db.query(
            Match
        )
        .filter(
            Match.date >= today,
            Match.status == "scheduled",
        )
        .order_by(
            Match.id.asc()
        )
        .all()
    )

    return [
        KnownBookmakerFixture(
            fixture_date=(
                row.date
            ),
            tournament=(
                row.tournament
                or "MODUS"
            ),
            player_a=(
                row.player_a
            ),
            player_b=(
                row.player_b
            ),
        )
        for row in rows
    ]


def build_paddy_power_capture_once():
    service = (
        PaddyPowerCaptureService()
    )

    def capture_once(
        db,
    ):
        fixtures = (
            _scheduled_modus_fixtures(
                db
            )
        )

        extractor = (
            PaddyPowerModusExtractor(
                fixtures
            )
        )

        return service.capture(
            db,
            source_url=(
                PADDY_POWER_MODUS_URL
            ),
            extractor=extractor,
        )

    return (
        capture_once,
        service,
    )


def run_paddy_power_live_capture(
    *,
    poll_seconds: float = 180.0,
    retry_seconds: float = 30.0,
    max_consecutive_failures: int = 5,
    max_cycles=None,
):
    capture_once, service = (
        build_paddy_power_capture_once()
    )

    manager = (
        BookmakerCaptureManager(
            capture_once=(
                capture_once
            ),
            poll_seconds=(
                poll_seconds
            ),
            retry_seconds=(
                retry_seconds
            ),
            max_consecutive_failures=(
                max_consecutive_failures
            ),
            stop_on_challenge=True,
        )
    )

    try:
        return manager.run_forever(
            session_factory=(
                SessionLocal
            ),
            max_cycles=(
                max_cycles
            ),
        )
    finally:
        service.close()
