from __future__ import annotations

from dataclasses import dataclass
import re

from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.services.chrome_browser_session import ChromeBrowserSession
from app.services.current_series_modus_fetcher import (
    CURRENT_GROUPS,
    _current_catalog_html,
)
from app.services.modus_fixture_lifecycle_service import (
    ModusFixtureLifecycleService,
)
from app.services.modus_historical_catalog_service import (
    ModusHistoricalCatalogService,
)


@dataclass(frozen=True)
class ModusMatchIdDiagnosticTarget:
    group: str
    source_url: str
    html_length: int
    raw_match_link_count: int
    unique_match_ids: tuple[int, ...]
    sample_links: tuple[str, ...]
    canonical_fixture_count: int
    canonical_fixture_ids: tuple[int, ...]
    message: str


@dataclass(frozen=True)
class ModusMatchIdDiagnosticReport:
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    targets: tuple[ModusMatchIdDiagnosticTarget, ...]
    total_raw_links: int
    total_unique_match_ids: int
    total_canonical_fixtures: int
    message: str


_LINK_PATTERN = re.compile(
    r"match-db-stats\.php\?match_id=(\d+)",
    re.IGNORECASE,
)

_FULL_LINK_PATTERN = re.compile(
    r"[^\"']*match-db-stats\.php\?match_id=\d+[^\"']*",
    re.IGNORECASE,
)


def _match_ids_from_html(html_text: str) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                int(value)
                for value in _LINK_PATTERN.findall(html_text or "")
            }
        )
    )


def _sample_links_from_html(
    html_text: str,
    *,
    limit: int = 10,
) -> tuple[str, ...]:
    links = []

    for value in _FULL_LINK_PATTERN.findall(html_text or ""):
        clean = str(value).strip()

        if clean not in links:
            links.append(clean)

        if len(links) >= limit:
            break

    return tuple(links)


def _canonical_fixture_ids(fixtures) -> tuple[int, ...]:
    values = []

    for fixture in fixtures:
        direct = getattr(fixture, "match_id", None)

        if direct is not None:
            try:
                values.append(int(direct))
                continue
            except Exception:
                pass

        provider_id = getattr(fixture, "provider_id", None)

        if provider_id:
            match = re.search(r"(\d+)", str(provider_id))
            if match:
                values.append(int(match.group(1)))
                continue

        source = getattr(fixture, "source", None)
        external_id = getattr(source, "external_id", None)

        if external_id:
            match = re.search(r"(\d+)", str(external_id))
            if match:
                values.append(int(match.group(1)))

    return tuple(sorted(set(values)))


def _latest_week(catalog):
    if not catalog.weeks:
        raise ValueError("MODUS catalogue has no weeks.")

    return max(
        catalog.weeks,
        key=lambda item: int(item.value),
    )


def run_modus_match_id_diagnostic(
    *,
    timeout_seconds: float = 30.0,
) -> ModusMatchIdDiagnosticReport:
    browser = ChromeBrowserSession()
    url_model = ModusUrlModel()
    catalog_service = ModusHistoricalCatalogService()
    lifecycle = ModusFixtureLifecycleService()

    try:
        catalog_html = _current_catalog_html(
            browser_session=browser,
            url_model=url_model,
            catalog_service=catalog_service,
            timeout_seconds=timeout_seconds,
        )

        catalog = catalog_service.parse(catalog_html)

        series = (
            catalog.selected_series
            or (catalog.series[0] if catalog.series else None)
        )

        if series is None:
            raise ValueError(
                "Current MODUS catalogue has no selected series."
            )

        week = _latest_week(catalog)
        targets = []

        for group in CURRENT_GROUPS:
            source_url = url_model.results_url(
                series_id=int(series.value),
                week_id=int(week.value),
                group=group,
            )

            browser.goto(
                source_url,
                timeout_seconds=timeout_seconds,
            )

            browser.wait_for(
                lambda: (
                    "match-db-stats.php?match_id="
                    in browser.html().casefold()
                    or "seriesselect"
                    in browser.html().casefold()
                ),
                timeout_seconds=timeout_seconds,
                description="MODUS results page",
            )

            html = browser.html()
            raw_ids = _match_ids_from_html(html)
            sample_links = _sample_links_from_html(html)

            try:
                preview = lifecycle.build_canonical_fixtures(html)
                fixtures = preview.fixtures
            except Exception:
                fixtures = []

            canonical_ids = _canonical_fixture_ids(fixtures)

            if raw_ids and not canonical_ids:
                message = (
                    "Raw MODUS match IDs are present in HTML but are not "
                    "surviving canonical fixture parsing."
                )
            elif raw_ids and canonical_ids:
                message = (
                    "Raw MODUS match IDs are present and canonical parser "
                    "retains at least some IDs."
                )
            elif not raw_ids:
                message = (
                    "No raw match-db-stats.php match IDs were found in the "
                    "captured page HTML."
                )
            else:
                message = "Diagnostic completed."

            targets.append(
                ModusMatchIdDiagnosticTarget(
                    group=str(group),
                    source_url=source_url,
                    html_length=len(html or ""),
                    raw_match_link_count=len(
                        _LINK_PATTERN.findall(html or "")
                    ),
                    unique_match_ids=raw_ids,
                    sample_links=sample_links,
                    canonical_fixture_count=len(fixtures),
                    canonical_fixture_ids=canonical_ids,
                    message=message,
                )
            )

        return ModusMatchIdDiagnosticReport(
            series_id=int(series.value),
            series_label=str(series.label),
            week_id=int(week.value),
            week_label=str(week.label),
            targets=tuple(targets),
            total_raw_links=sum(
                target.raw_match_link_count
                for target in targets
            ),
            total_unique_match_ids=len(
                {
                    match_id
                    for target in targets
                    for match_id in target.unique_match_ids
                }
            ),
            total_canonical_fixtures=sum(
                target.canonical_fixture_count
                for target in targets
            ),
            message=(
                "MODUS match-ID extraction diagnostic completed without "
                "writing any mappings."
            ),
        )

    finally:
        browser.close()
