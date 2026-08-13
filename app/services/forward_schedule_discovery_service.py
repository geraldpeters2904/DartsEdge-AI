from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.match import Match
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
class ForwardScheduleTargetResult:
    group: str
    state: str
    imported: bool
    unchanged: bool
    source_url: Optional[str]
    current_url: Optional[str]
    page_title: Optional[str]
    fixture_count: Optional[int]
    message: str
    error: Optional[str] = None


@dataclass(frozen=True)
class ForwardScheduleDiscoveryReport:
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    targets: int
    imported: int
    unchanged: int
    failed: int
    future_fixtures: int
    message: str
    target_results: Tuple[
        ForwardScheduleTargetResult,
        ...
    ] = ()


def _latest_week(catalog):
    if not catalog.weeks:
        raise ValueError(
            "MODUS catalogue has no weeks."
        )

    return max(
        catalog.weeks,
        key=lambda item: int(
            item.value
        ),
    )


def _future_modus_fixture_count(
    db: Session,
    *,
    today: Optional[date] = None,
) -> int:
    """
    Count actionable scheduled MODUS fixtures.

    Despite the legacy function/field name, today's scheduled
    fixtures are intentionally included because MODUS often
    publishes fixtures shortly before play.
    """
    current_day = (
        today
        or date.today()
    )

    return int(
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= current_day,
            Match.tournament.ilike("%MODUS%"),
        )
        .count()
    )


def _target_success_result(
    *,
    group: str,
    result,
) -> ForwardScheduleTargetResult:
    import_result = getattr(
        result,
        "import_result",
        None,
    )

    fixture_count = (
        int(
            import_result.fixture_count
        )
        if (
            import_result is not None
            and getattr(
                import_result,
                "fixture_count",
                None,
            )
            is not None
        )
        else None
    )

    state = (
        "IMPORTED"
        if result.imported
        else (
            "UNCHANGED"
            if result.unchanged
            else str(
                getattr(
                    result,
                    "action",
                    "UNKNOWN",
                )
            ).upper()
        )
    )

    return ForwardScheduleTargetResult(
        group=group,
        state=state,
        imported=bool(
            result.imported
        ),
        unchanged=bool(
            result.unchanged
        ),
        source_url=getattr(
            result,
            "source_url",
            None,
        ),
        current_url=getattr(
            result,
            "current_url",
            None,
        ),
        page_title=getattr(
            result,
            "page_title",
            None,
        ),
        fixture_count=fixture_count,
        message=str(
            getattr(
                result,
                "message",
                "",
            )
        ),
        error=None,
    )


def _target_failure_result(
    *,
    group: str,
    exc: Exception,
) -> ForwardScheduleTargetResult:
    return ForwardScheduleTargetResult(
        group=group,
        state="FAILED",
        imported=False,
        unchanged=False,
        source_url=None,
        current_url=None,
        page_title=None,
        fixture_count=None,
        message=(
            f"{group} discovery failed."
        ),
        error=(
            f"{type(exc).__name__}: {exc}"
        ),
    )


def run_forward_schedule_discovery(
    *,
    timeout_seconds: float = 30.0,
) -> ForwardScheduleDiscoveryReport:
    browser = ChromeBrowserSession()
    catalog_service = (
        ModusHistoricalCatalogService()
    )
    url_model = ModusUrlModel()

    discovery = (
        ModusFixtureDiscoveryService(
            browser_session=browser,
            url_model=url_model,
            timeout_seconds=(
                timeout_seconds
            ),
        )
    )

    db = SessionLocal()

    try:
        catalog_html = (
            _current_catalog_html(
                browser_session=browser,
                url_model=url_model,
                catalog_service=(
                    catalog_service
                ),
                timeout_seconds=(
                    timeout_seconds
                ),
            )
        )

        catalog = (
            catalog_service.parse(
                catalog_html
            )
        )

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
                "Current MODUS catalogue "
                "has no series."
            )

        week = _latest_week(
            catalog
        )

        imported = 0
        unchanged = 0
        failed = 0
        target_results = []

        for group in CURRENT_GROUPS:
            try:
                result = (
                    discovery.discover(
                        db,
                        series_id=int(
                            series.value
                        ),
                        week_id=int(
                            week.value
                        ),
                        group=group,
                    )
                )

                target_results.append(
                    _target_success_result(
                        group=group,
                        result=result,
                    )
                )

                if result.imported:
                    imported += 1
                elif result.unchanged:
                    unchanged += 1

            except Exception as exc:
                failed += 1

                target_results.append(
                    _target_failure_result(
                        group=group,
                        exc=exc,
                    )
                )

        future_fixtures = (
            _future_modus_fixture_count(
                db
            )
        )

        targets = len(
            CURRENT_GROUPS
        )

        if future_fixtures:
            message = (
                f"Forward schedule discovery "
                f"found {future_fixtures} "
                f"current/future MODUS fixture(s)."
            )
        elif failed:
            message = (
                "No current/future MODUS fixtures "
                "were confirmed, and "
                f"{failed} of {targets} target(s) "
                "failed discovery."
            )
        else:
            message = (
                "No current or future MODUS fixtures "
                "are currently published in the "
                "latest available week."
            )

        return ForwardScheduleDiscoveryReport(
            series_id=int(
                series.value
            ),
            series_label=str(
                series.label
            ),
            week_id=int(
                week.value
            ),
            week_label=str(
                week.label
            ),
            targets=targets,
            imported=imported,
            unchanged=unchanged,
            failed=failed,
            future_fixtures=(
                future_fixtures
            ),
            message=message,
            target_results=tuple(
                target_results
            ),
        )

    finally:
        try:
            db.close()
        finally:
            discovery.close()
