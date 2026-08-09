from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.db import SessionLocal
from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.services.chrome_browser_session import ChromeBrowserSession
from app.services.current_series_modus_fetcher import (
    CURRENT_GROUPS,
    _current_catalog_html,
)
from app.services.modus_fixture_discovery_service import (
    ModusFixtureDiscoveryService,
)
from app.services.modus_historical_catalog_service import (
    ModusHistoricalCatalogService,
)


@dataclass(frozen=True)
class CurrentSeriesCatchupReport:
    series_id: int
    series_label: str
    weeks: int
    targets: int
    imported: int
    unchanged: int
    failed: int
    fixtures_seen: int
    scheduled_seen: int
    completed_seen: int
    message: str


def run_current_series_catchup(
    *,
    timeout_seconds: float = 30.0,
) -> CurrentSeriesCatchupReport:
    browser = ChromeBrowserSession()
    catalog_service = ModusHistoricalCatalogService()
    url_model = ModusUrlModel()
    discovery = ModusFixtureDiscoveryService(
        browser_session=browser,
        url_model=url_model,
        timeout_seconds=timeout_seconds,
    )
    db = SessionLocal()

    try:
        html = _current_catalog_html(
            browser_session=browser,
            url_model=url_model,
            catalog_service=catalog_service,
            timeout_seconds=timeout_seconds,
        )

        catalog = catalog_service.parse(html)

        series = (
            catalog.selected_series
            or (
                catalog.series[0]
                if catalog.series
                else None
            )
        )

        if series is None:
            raise ValueError(
                "Current MODUS catalogue has no selected series."
            )

        weeks = tuple(
            catalog.weeks
        )

        if not weeks:
            raise ValueError(
                "Current MODUS series has no weeks."
            )

        imported = 0
        unchanged = 0
        failed = 0
        fixtures_seen = 0
        scheduled_seen = 0
        completed_seen = 0

        for week in weeks:
            for group in CURRENT_GROUPS:
                try:
                    result = discovery.discover(
                        db,
                        series_id=int(series.value),
                        week_id=int(week.value),
                        group=group,
                    )

                    if result.imported:
                        imported += 1
                    elif result.unchanged:
                        unchanged += 1

                    if result.import_result is not None:
                        fixtures_seen += int(
                            result.import_result.fixture_count
                        )
                        scheduled_seen += int(
                            result.import_result.scheduled_count
                        )
                        completed_seen += int(
                            result.import_result.completed_count
                        )

                except Exception:
                    failed += 1

        targets = (
            len(weeks)
            * len(CURRENT_GROUPS)
        )

        return CurrentSeriesCatchupReport(
            series_id=int(series.value),
            series_label=str(series.label),
            weeks=len(weeks),
            targets=targets,
            imported=imported,
            unchanged=unchanged,
            failed=failed,
            fixtures_seen=fixtures_seen,
            scheduled_seen=scheduled_seen,
            completed_seen=completed_seen,
            message=(
                f"Current-series catch-up scanned {targets} target(s) "
                f"across {len(weeks)} week(s)."
            ),
        )

    finally:
        try:
            db.close()
        finally:
            discovery.close()
