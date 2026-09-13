from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot

from app.services.bookmaker_capture_types import (
    BookmakerCaptureReport,
)

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
    normalise_name,
)
from app.services.paddy_power_event_extractor import (
    PaddyPowerEventExtractor,
)


PADDY_POWER_MODUS_URL = (
    "https://www.paddypower.com/darts/"
    "modus-super-series"
)



PADDY_POWER_EVENT_MARKETS = frozenset(
    {
        "match_winner",
        "total_legs",
        "handicap",
        "most_180s",
        "total_180s",
        "player_total_180s",
    }
)

PADDY_POWER_COMPLETE_EVENT_POLL_SECONDS = 15 * 60

_EVENT_LAST_POLLED_AT = {}


def _fixture_poll_key(
    fixture: KnownBookmakerFixture,
):
    players = sorted(
        (
            normalise_name(fixture.player_a),
            normalise_name(fixture.player_b),
        )
    )

    return (
        fixture.fixture_date.isoformat(),
        players[0],
        players[1],
    )


def _resolve_known_fixture_match(
    db,
    fixture: KnownBookmakerFixture,
):
    try:
        candidates = (
            db.query(Match)
            .filter(
                Match.date == fixture.fixture_date
            )
            .order_by(
                Match.id.asc()
            )
            .all()
        )
    except Exception:
        return None

    player_a = normalise_name(
        fixture.player_a
    )
    player_b = normalise_name(
        fixture.player_b
    )

    matches = [
        row
        for row in candidates
        if (
            (
                normalise_name(row.player_a)
                == player_a
                and normalise_name(row.player_b)
                == player_b
            )
            or (
                normalise_name(row.player_a)
                == player_b
                and normalise_name(row.player_b)
                == player_a
            )
        )
    ]

    if len(matches) == 1:
        return matches[0]

    return None


def _known_event_markets(
    db,
    fixture_id: int,
):
    try:
        rows = (
            db.query(
                OddsSnapshot.market
            )
            .filter(
                OddsSnapshot.fixture_id
                == int(fixture_id),
                OddsSnapshot.bookmaker_code
                == "paddypower",
            )
            .distinct()
            .all()
        )
    except Exception:
        return set()

    return {
        row[0]
        for row in rows
        if row
        and row[0]
    }


def _should_poll_event_fixture(
    db,
    fixture: KnownBookmakerFixture,
    *,
    now=None,
) -> bool:
    match = _resolve_known_fixture_match(
        db,
        fixture,
    )

    if match is None:
        return True

    markets = _known_event_markets(
        db,
        match.id,
    )

    if not PADDY_POWER_EVENT_MARKETS.issubset(
        markets
    ):
        return True

    checked_at = _EVENT_LAST_POLLED_AT.get(
        _fixture_poll_key(fixture)
    )

    if checked_at is None:
        return True

    current = now or datetime.utcnow()

    return (
        current - checked_at
        >= timedelta(
            seconds=(
                PADDY_POWER_COMPLETE_EVENT_POLL_SECONDS
            )
        )
    )


def _mark_event_fixture_polled(
    fixture: KnownBookmakerFixture,
    *,
    now=None,
) -> None:
    _EVENT_LAST_POLLED_AT[
        _fixture_poll_key(fixture)
    ] = (
        now
        or datetime.utcnow()
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
    browser = ChromeBrowserSession(headless=True)

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
            page_ready=(
                paddy_power_modus_page_ready
            ),
        )

    return (
        capture_once,
        service,
    )


def paddy_power_modus_page_ready(
    html: str,
) -> bool:
    lowered = (html or "").casefold()

    return (
        "modus super series"
        in lowered
        and (
            "match odds"
            in lowered
            or "fixtures"
            in lowered
        )
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
    service=None,
):
    if service is None:
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
    *,
    category_html=None,
    service=None,
):
    fixtures = (
        _scheduled_modus_fixtures(
            db
        )
    )

    if category_html is None:
        category_html = (
            load_paddy_power_modus_category_html()
        )

    kwargs = {}

    if service is not None:
        kwargs["service"] = service

    return capture_discovered_paddy_power_events(
        db,
        fixtures=fixtures,
        category_html=category_html,
        **kwargs,
    )


def capture_discovered_paddy_power_events(
    db,
    *,
    fixtures,
    category_html: str,
    service=None,
):
    reports = []

    for fixture in fixtures:
        if not _should_poll_event_fixture(
            db,
            fixture,
        ):
            continue

        source_url = discover_fixture_event_url(
            category_html,
            fixture,
        )

        if source_url is None:
            continue

        builder_kwargs = {
            "fixture": fixture,
            "source_url": source_url,
        }

        if service is not None:
            builder_kwargs["service"] = service

        capture_once, event_service = (
            build_paddy_power_event_capture_once(
                **builder_kwargs
            )
        )

        try:
            reports.append(
                capture_once(db)
            )

            _mark_event_fixture_polled(
                fixture
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
            if service is None:
                event_service.close()

    return reports


def capture_paddy_power_discovered_events_report_once(
    db,
    *,
    category_html=None,
    service=None,
):
    kwargs = {}

    if category_html is not None:
        kwargs["category_html"] = category_html

    if service is not None:
        kwargs["service"] = service

    reports = (
        capture_paddy_power_discovered_events_once(
            db,
            **kwargs,
        )
    )

    captured_at = datetime.utcnow()

    if reports:
        captured_at = max(
            report.captured_at
            for report in reports
        )

    return BookmakerCaptureReport(
        bookmaker="Paddy Power",
        source_url=PADDY_POWER_MODUS_URL,
        captured_at=captured_at,
        extracted_prices=sum(
            report.extracted_prices
            for report in reports
        ),
        stored_prices=sum(
            report.stored_prices
            for report in reports
        ),
        unchanged_prices=sum(
            report.unchanged_prices
            for report in reports
        ),
        skipped_prices=sum(
            report.skipped_prices
            for report in reports
        ),
        challenge_detected=any(
            report.challenge_detected
            for report in reports
        ),
        message=(
            "Paddy Power discovered event capture completed."
        ),
    )



def run_paddy_power_live_capture(
    *,
    poll_seconds: float = 180.0,
    retry_seconds: float = 30.0,
    max_consecutive_failures: int = 5,
    max_cycles=None,
):
    manager = (
        BookmakerCaptureManager(
            capture_once=(
                capture_paddy_power_discovered_events_report_once
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

    return manager.run_forever(
        session_factory=(
            SessionLocal
        ),
        max_cycles=(
            max_cycles
        ),
    )
