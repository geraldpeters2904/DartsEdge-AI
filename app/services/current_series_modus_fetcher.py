from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from app.db import SessionLocal
from app.models.match import Match
from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.services.chrome_browser_session import ChromeBrowserSession
from app.services.modus_fixture_discovery_service import ModusFixtureDiscoveryService
from app.services.modus_historical_catalog_service import ModusHistoricalCatalogService


CURRENT_GROUPS = (
    "Group A",
    "Group B",
    "Group C",
    "Final",
)


@dataclass(frozen=True)
class CurrentModusTarget:
    series_id: int
    week_id: int
    group: str


def _catalog_ready(
    browser_session: ChromeBrowserSession,
    catalog_service: ModusHistoricalCatalogService,
) -> bool:
    try:
        catalog = catalog_service.parse(browser_session.html())
    except Exception:
        return False

    return bool(
        catalog.series
        and catalog.weeks
    )


def _current_catalog_html(
    *,
    browser_session: ChromeBrowserSession,
    url_model: ModusUrlModel,
    catalog_service: ModusHistoricalCatalogService,
    timeout_seconds: float,
) -> str:
    source_url = (
        f"{url_model.base_url.rstrip('/')}/results"
    )

    browser_session.goto(
        source_url,
        timeout_seconds=timeout_seconds,
    )

    browser_session.wait_for(
        lambda: _catalog_ready(
            browser_session,
            catalog_service,
        ),
        timeout_seconds=timeout_seconds,
        description="current MODUS catalogue selectors",
    )

    return browser_session.html()


def _targets_from_catalog(
    html_text: str,
    *,
    catalog_service: Optional[
        ModusHistoricalCatalogService
    ] = None,
) -> tuple[CurrentModusTarget, ...]:
    service = (
        catalog_service
        or ModusHistoricalCatalogService()
    )

    catalog = service.parse(
        html_text
    )

    series = (
        catalog.selected_series
        or (
            catalog.series[0]
            if catalog.series
            else None
        )
    )

    week = (
        catalog.selected_week
        or (
            catalog.weeks[0]
            if catalog.weeks
            else None
        )
    )

    if series is None:
        raise ValueError(
            "Current MODUS catalogue has no series."
        )

    if week is None:
        raise ValueError(
            "Current MODUS catalogue has no week."
        )

    # Every standard MODUS week is polled across the four lifecycle pages.
    # We do not rely on which individual group button happens to be marked
    # active on the landing page.
    return tuple(
        CurrentModusTarget(
            series_id=int(
                series.value
            ),
            week_id=int(
                week.value
            ),
            group=group,
        )
        for group in CURRENT_GROUPS
    )


def _matches_for_window(
    db,
    *,
    window_start: date,
    window_end: date,
) -> list[Match]:
    return (
        db.query(Match)
        .filter(
            Match.date >= window_start,
            Match.date <= window_end,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .all()
    )


def fetch_current_modus_matches(
    window_start: date,
    window_end: date,
) -> Iterable[object]:
    browser = (
        ChromeBrowserSession()
    )

    catalog_service = (
        ModusHistoricalCatalogService()
    )

    url_model = (
        ModusUrlModel()
    )

    discovery = (
        ModusFixtureDiscoveryService(
            browser_session=browser,
            url_model=url_model,
        )
    )

    db = SessionLocal()

    try:
        catalog_html = (
            _current_catalog_html(
                browser_session=browser,
                url_model=url_model,
                catalog_service=catalog_service,
                timeout_seconds=30.0,
            )
        )

        targets = (
            _targets_from_catalog(
                catalog_html,
                catalog_service=catalog_service,
            )
        )

        for target in targets:
            discovery.discover(
                db,
                series_id=target.series_id,
                week_id=target.week_id,
                group=target.group,
            )

        return list(
            _matches_for_window(
                db,
                window_start=window_start,
                window_end=window_end,
            )
        )

    finally:
        try:
            db.close()
        finally:
            discovery.close()
