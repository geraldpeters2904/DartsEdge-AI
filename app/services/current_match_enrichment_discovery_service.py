
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.match import Match
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
class EnrichmentCandidate:
    internal_match_id: int
    fixture_date: date
    player_a: str
    player_b: str
    stage: Optional[str]
    resolved_modus_match_id: Optional[int]
    candidate_modus_match_ids: tuple[int, ...]
    status: str
    message: str


@dataclass(frozen=True)
class CurrentMatchEnrichmentDiscoveryReport:
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    targets_scanned: int
    completed_without_performance: int
    resolved: int
    ambiguous: int
    unresolved: int
    candidates: tuple[EnrichmentCandidate, ...]
    message: str


def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _fixture_key(
    player_a: str,
    player_b: str,
) -> frozenset[str]:
    return frozenset(
        (
            _normalise(player_a),
            _normalise(player_b),
        )
    )


def _external_match_id(value) -> Optional[int]:
    if value is None:
        return None

    match = re.search(
        r"(\d+)",
        str(value),
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def _fixture_date(fixture) -> Optional[date]:
    for name in (
        "fixture_date",
        "date",
        "match_date",
    ):
        value = getattr(
            fixture,
            name,
            None,
        )

        if value is None:
            continue

        if isinstance(
            value,
            date,
        ):
            return value

        try:
            return date.fromisoformat(
                str(value)[:10]
            )
        except Exception:
            continue

    return None


def _fixture_stage(fixture) -> str:
    return _normalise(
        getattr(
            fixture,
            "stage",
            None,
        )
    )


def _fixture_match_id(fixture) -> Optional[int]:
    direct = getattr(
        fixture,
        "match_id",
        None,
    )

    if direct is not None:
        try:
            return int(
                direct
            )
        except Exception:
            pass

    provider_id = getattr(
        fixture,
        "provider_id",
        None,
    )

    value = _external_match_id(
        provider_id
    )

    if value is not None:
        return value

    source = getattr(
        fixture,
        "source",
        None,
    )

    external_id = getattr(
        source,
        "external_id",
        None,
    )

    return _external_match_id(
        external_id
    )


def _completed_without_performance(
    db: Session,
    *,
    since: date,
    limit: int,
) -> list[Match]:
    table_names = set(
        inspect(
            db.get_bind()
        ).get_table_names()
    )

    if (
        "player_match_performances"
        not in table_names
    ):
        raise ValueError(
            "player_match_performances table was not found."
        )

    ids = [
        int(row[0])
        for row in db.execute(
            text(
                """
                SELECT m.id
                FROM matches m
                WHERE m.status = 'completed'
                  AND lower(m.tournament) LIKE '%modus%'
                  AND m.date >= :since
                  AND NOT EXISTS (
                      SELECT 1
                      FROM player_match_performances p
                      WHERE p.match_id = m.id
                  )
                ORDER BY m.date DESC, m.id DESC
                LIMIT :limit
                """
            ),
            {
                "since": since.isoformat(),
                "limit": max(
                    1,
                    int(limit),
                ),
            },
        ).fetchall()
    ]

    if not ids:
        return []

    rows = (
        db.query(Match)
        .filter(
            Match.id.in_(ids)
        )
        .all()
    )

    by_id = {
        int(row.id): row
        for row in rows
    }

    return [
        by_id[match_id]
        for match_id in ids
        if match_id in by_id
    ]


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


def _canonical_page_fixtures(
    html_text: str,
):
    return (
        ModusFixtureLifecycleService()
        .build_canonical_fixtures(
            html_text
        )
        .fixtures
    )


def run_current_match_enrichment_discovery(
    *,
    recent_days: int = 14,
    limit: int = 100,
    timeout_seconds: float = 30.0,
) -> CurrentMatchEnrichmentDiscoveryReport:
    db = SessionLocal()
    browser = ChromeBrowserSession()
    url_model = ModusUrlModel()
    catalog_service = (
        ModusHistoricalCatalogService()
    )

    try:
        since = (
            date.today()
            - timedelta(
                days=max(
                    1,
                    int(recent_days),
                )
            )
        )

        missing = (
            _completed_without_performance(
                db,
                since=since,
                limit=limit,
            )
        )

        catalog_html = (
            _current_catalog_html(
                browser_session=browser,
                url_model=url_model,
                catalog_service=catalog_service,
                timeout_seconds=timeout_seconds,
            )
        )

        catalog = catalog_service.parse(
            catalog_html
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
                "Current MODUS catalogue has no series."
            )

        week = _latest_week(
            catalog
        )

        official = []

        for group in CURRENT_GROUPS:
            source_url = (
                url_model.results_url(
                    series_id=int(
                        series.value
                    ),
                    week_id=int(
                        week.value
                    ),
                    group=group,
                )
            )

            browser.goto(
                source_url,
                timeout_seconds=timeout_seconds,
            )

            browser.wait_for(
                lambda: (
                    "match-db-stats.php?match_id="
                    in browser.html().casefold()
                ),
                timeout_seconds=timeout_seconds,
                description="MODUS fixture cards",
            )

            official.extend(
                _canonical_page_fixtures(
                    browser.html()
                )
            )

        output = []

        for match in missing:
            key = _fixture_key(
                match.player_a,
                match.player_b,
            )

            same_pair = [
                fixture
                for fixture in official
                if (
                    _fixture_key(
                        getattr(
                            fixture,
                            "player_a",
                            "",
                        ),
                        getattr(
                            fixture,
                            "player_b",
                            "",
                        ),
                    )
                    == key
                )
            ]

            same_date = [
                fixture
                for fixture in same_pair
                if (
                    _fixture_date(
                        fixture
                    )
                    in {
                        None,
                        match.date,
                    }
                )
            ]

            stage = _normalise(
                getattr(
                    match,
                    "stage",
                    None,
                )
            )

            stage_matches = [
                fixture
                for fixture in same_date
                if (
                    not stage
                    or not _fixture_stage(
                        fixture
                    )
                    or _fixture_stage(
                        fixture
                    )
                    == stage
                )
            ]

            pool = (
                stage_matches
                if stage_matches
                else same_date
            )

            candidate_ids = tuple(
                sorted(
                    {
                        match_id
                        for match_id in (
                            _fixture_match_id(
                                fixture
                            )
                            for fixture in pool
                        )
                        if match_id is not None
                    }
                )
            )

            if len(
                candidate_ids
            ) == 1:
                status = "resolved"
                resolved = (
                    candidate_ids[0]
                )
                message = (
                    "One unambiguous official MODUS match ID was resolved."
                )
            elif len(
                candidate_ids
            ) > 1:
                status = "ambiguous"
                resolved = None
                message = (
                    "Multiple official MODUS match IDs match this internal fixture; "
                    "no mapping was guessed."
                )
            else:
                status = "unresolved"
                resolved = None
                message = (
                    "No official MODUS match ID could be resolved from the "
                    "latest current-series result pages."
                )

            output.append(
                EnrichmentCandidate(
                    internal_match_id=int(
                        match.id
                    ),
                    fixture_date=match.date,
                    player_a=match.player_a,
                    player_b=match.player_b,
                    stage=getattr(
                        match,
                        "stage",
                        None,
                    ),
                    resolved_modus_match_id=resolved,
                    candidate_modus_match_ids=candidate_ids,
                    status=status,
                    message=message,
                )
            )

        resolved_count = sum(
            row.status == "resolved"
            for row in output
        )

        ambiguous_count = sum(
            row.status == "ambiguous"
            for row in output
        )

        unresolved_count = sum(
            row.status == "unresolved"
            for row in output
        )

        return (
            CurrentMatchEnrichmentDiscoveryReport(
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
                targets_scanned=len(
                    CURRENT_GROUPS
                ),
                completed_without_performance=len(
                    missing
                ),
                resolved=resolved_count,
                ambiguous=ambiguous_count,
                unresolved=unresolved_count,
                candidates=tuple(
                    output
                ),
                message=(
                    "Current match enrichment discovery completed without "
                    "writing provider mappings."
                ),
            )
        )

    finally:
        try:
            db.close()
        finally:
            browser.close()
