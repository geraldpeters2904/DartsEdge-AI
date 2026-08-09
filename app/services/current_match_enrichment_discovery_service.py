
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
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



def _external_match_id(value):
    if value is None:
        return None

    import re

    match = re.search(
        r"(\d+)",
        str(value),
    )

    if not match:
        return None

    return int(
        match.group(1)
    )

def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _pair_key(
    player_a: str,
    player_b: str,
) -> frozenset[str]:
    return frozenset(
        (
            _normalise(player_a),
            _normalise(player_b),
        )
    )


def _canonical_pair_key(fixture) -> frozenset[str]:
    return _pair_key(
        getattr(
            fixture,
            "player_a_name",
            "",
        ),
        getattr(
            fixture,
            "player_b_name",
            "",
        ),
    )


def _canonical_stage(fixture) -> str:
    return _normalise(
        getattr(
            fixture,
            "stage",
            None,
        )
        or getattr(
            fixture,
            "group",
            None,
        )
    )


def _canonical_match_id(
    fixture,
) -> Optional[int]:
    external_id = getattr(
        fixture,
        "external_id",
        None,
    )

    if external_id:
        digits = "".join(
            ch
            for ch in str(external_id)
            if ch.isdigit()
        )

        if digits:
            return int(digits)

    source = getattr(
        fixture,
        "source",
        None,
    )

    source_external_id = getattr(
        source,
        "external_id",
        None,
    )

    if source_external_id:
        digits = "".join(
            ch
            for ch in str(
                source_external_id
            )
            if ch.isdigit()
        )

        if digits:
            return int(digits)

    return None


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
                ORDER BY m.date ASC, m.id ASC
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


def _official_groups(
    fixtures,
):
    grouped = defaultdict(
        list
    )

    for fixture in fixtures:
        match_id = (
            _canonical_match_id(
                fixture
            )
        )

        if match_id is None:
            continue

        key = (
            _canonical_stage(
                fixture
            ),
            _canonical_pair_key(
                fixture
            ),
        )

        grouped[key].append(
            (
                match_id,
                fixture,
            )
        )

    for key in grouped:
        grouped[key].sort(
            key=lambda item: item[0]
        )

    return grouped


def _internal_groups(
    matches,
):
    grouped = defaultdict(
        list
    )

    for match in matches:
        key = (
            _normalise(
                getattr(
                    match,
                    "stage",
                    None,
                )
            ),
            _pair_key(
                match.player_a,
                match.player_b,
            ),
        )

        grouped[key].append(
            match
        )

    for key in grouped:
        grouped[key].sort(
            key=lambda row: int(
                row.id
            )
        )

    return grouped


def _resolve_by_occurrence(
    internal_matches,
    official_matches,
):
    results = {}

    internal_count = len(
        internal_matches
    )

    official_count = len(
        official_matches
    )

    if internal_count == 0:
        return results

    if official_count == 0:
        for match in internal_matches:
            results[int(match.id)] = (
                None,
                (),
                "unresolved",
                (
                    "No official MODUS fixture matched this player pair "
                    "and stage/group."
                ),
            )
        return results

    candidate_ids = tuple(
        match_id
        for match_id, _fixture
        in official_matches
    )

    if internal_count == official_count:
        for match, (
            official_id,
            _fixture,
        ) in zip(
            internal_matches,
            official_matches,
        ):
            results[int(match.id)] = (
                official_id,
                (
                    official_id,
                ),
                "resolved",
                (
                    "Resolved by occurrence order within the same "
                    "player pair and stage/group."
                ),
            )

        return results

    if (
        internal_count == 1
        and official_count == 1
    ):
        match = internal_matches[0]
        official_id = (
            official_matches[0][0]
        )

        results[int(match.id)] = (
            official_id,
            (
                official_id,
            ),
            "resolved",
            (
                "One unambiguous official MODUS fixture matched the "
                "player pair and stage/group."
            ),
        )

        return results

    for match in internal_matches:
        results[int(match.id)] = (
            None,
            candidate_ids,
            "ambiguous",
            (
                "The number of internal and official occurrences differs "
                "for this player pair/stage, so no mapping was guessed."
            ),
        )

    return results


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
    lifecycle = (
        ModusFixtureLifecycleService()
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

        official_fixtures = []

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

            preview = (
                lifecycle
                .build_canonical_fixtures(
                    browser.html()
                )
            )

            official_fixtures.extend(
                preview.fixtures
            )

        internal_groups = (
            _internal_groups(
                missing
            )
        )

        official_groups = (
            _official_groups(
                official_fixtures
            )
        )

        resolutions = {}

        all_keys = set(
            internal_groups
        )

        for key in all_keys:
            internal_rows = (
                internal_groups.get(
                    key,
                    [],
                )
            )

            official_rows = (
                official_groups.get(
                    key,
                    [],
                )
            )

            resolutions.update(
                _resolve_by_occurrence(
                    internal_rows,
                    official_rows,
                )
            )

        output = []

        for match in missing:
            (
                resolved_id,
                candidate_ids,
                status,
                message,
            ) = resolutions.get(
                int(
                    match.id
                ),
                (
                    None,
                    (),
                    "unresolved",
                    (
                        "No official resolution was produced "
                        "for this fixture."
                    ),
                ),
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
                    resolved_modus_match_id=resolved_id,
                    candidate_modus_match_ids=tuple(
                        candidate_ids
                    ),
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
                    "Current match enrichment discovery completed using "
                    "pair/stage occurrence matching without writing mappings."
                ),
            )
        )

    finally:
        try:
            db.close()
        finally:
            browser.close()

# Backward compatibility helpers

def _fixture_key(
    player_a: str,
    player_b: str,
):
    def clean(value):
        return " ".join(
            (value or "")
            .strip()
            .casefold()
            .split()
        )

    return frozenset(
        (
            clean(player_a),
            clean(player_b),
        )
    )

