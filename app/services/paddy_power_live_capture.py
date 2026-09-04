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
from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)
from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
    PaddyPowerModusExtractor,
    discover_fixture_event_url,
)
from app.services.paddy_power_event_extractor import (
    PaddyPowerEventExtractor,
)


PADDY_POWER_MODUS_URL = (
    "https://www.paddypower.com/darts/"
    "modus-super-series"
)


def paddy_power_modus_category_ready(
    html: str,
) -> bool:
    lowered = (
        html
        or ""
    ).casefold()

    return (
        "/darts/modus-super-series/"
        in lowered
        and "-v-"
        in lowered
    )


def load_paddy_power_modus_category_html(
    *,
    timeout_seconds: float = 30.0,
) -> str:
    browser = ChromeBrowserSession()

    try:
        browser.goto(
            PADDY_POWER_MODUS_URL,
            timeout_seconds=timeout_seconds,
        )

        browser.wait_for(
            lambda: (
                paddy_power_modus_category_ready(
                    browser.html()
                )
            ),
            timeout_seconds=timeout_seconds,
            description=(
                "rendered Paddy Power MODUS fixtures"
            ),
        )

        return browser.html()

    finally:
        browser.close()


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


def paddy_power_event_page_ready(
    html: str,
) -> bool:
    return (
        'class="event-card--item'
        in (html or "").casefold()
    )


def build_paddy_power_event_capture_once(
    *,
    fixture: KnownBookmakerFixture,
    source_url: str,
):
    service = PaddyPowerCaptureService()

    def capture_once(
        db,
    ):
        extractor = PaddyPowerEventExtractor(
            fixture
        )
        return service.capture(
            db,
            source_url=source_url,
            extractor=extractor,
            page_ready=(
                paddy_power_event_page_ready
            ),
        )

    return (
        capture_once,
        service,
    )


def capture_paddy_power_discovered_events_once(
    db,
):
    fixtures = (
        _scheduled_modus_fixtures(
            db
        )
    )

    category_html = (
        load_paddy_power_modus_category_html()
    )

    return (
        capture_discovered_paddy_power_events(
            db,
            fixtures=fixtures,
            category_html=category_html,
        )
    )


def capture_discovered_paddy_power_events(
    db,
    *,
    fixtures,
    category_html: str,
):
    reports = []

    for fixture in fixtures:
        source_url = discover_fixture_event_url(
            category_html,
            fixture,
        )

        if source_url is None:
            continue

        capture_once, service = (
            build_paddy_power_event_capture_once(
                fixture=fixture,
                source_url=source_url,
            )
        )

        try:
            reports.append(
                capture_once(db)
            )
        except Exception:
            rollback = getattr(
                db,
                "rollback",
                None,
            )

            if callable(rollback):
                rollback()
        finally:
            service.close()

    return reports


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
