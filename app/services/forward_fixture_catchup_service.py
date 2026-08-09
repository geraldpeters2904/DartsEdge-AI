from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match


@dataclass(frozen=True)
class CatchupCandidate:
    fixture_id: int
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    days_stale: int
    has_fixture_mapping: bool
    classification: str


@dataclass(frozen=True)
class CatchupResolution:
    ready: bool
    module_name: Optional[str]
    function_name: Optional[str]
    callable: Optional[Callable[..., Any]]
    message: str


@dataclass(frozen=True)
class CatchupRunReport:
    candidates: int
    attempted: int
    completed: int
    unchanged: int
    failed: int
    message: str


CANDIDATE_MODULES = (
    "app.services.fixture_lifecycle_service",
    "app.services.fixture_completion_service",
    "app.services.modus_fixture_lifecycle_service",
)

CANDIDATE_FUNCTIONS = (
    "refresh_fixture",
    "refresh_match",
    "catch_up_fixture",
    "settle_fixture",
    "update_fixture_lifecycle",
    "process_fixture",
)


def _has_fixture_mapping(
    db: Session,
    fixture_id: int,
) -> bool:
    return (
        db.query(ProviderEntityMapping)
        .filter(
            ProviderEntityMapping.entity_type == "fixture",
            ProviderEntityMapping.internal_id == int(fixture_id),
        )
        .first()
        is not None
    )


def stale_scheduled_modus_fixtures(
    db: Session,
    *,
    today: Optional[date] = None,
    limit: int = 100,
) -> tuple[CatchupCandidate, ...]:
    current_day = (
        today
        or date.today()
    )

    rows = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date < current_day,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .limit(
            max(
                1,
                int(limit),
            )
        )
        .all()
    )

    output = []

    for row in rows:
        tournament = (
            row.tournament
            or ""
        )

        if (
            "modus"
            not in tournament.casefold()
        ):
            continue

        mapped = _has_fixture_mapping(
            db,
            row.id,
        )

        output.append(
            CatchupCandidate(
                fixture_id=int(
                    row.id
                ),
                fixture_date=row.date,
                tournament=tournament,
                player_a=row.player_a,
                player_b=row.player_b,
                days_stale=max(
                    0,
                    (
                        current_day
                        - row.date
                    ).days,
                ),
                has_fixture_mapping=mapped,
                classification=(
                    "CANONICAL_STALE"
                    if mapped
                    else "LEGACY_ORPHAN"
                ),
            )
        )

    return tuple(
        output
    )


def resolve_fixture_refresh_callable(
) -> CatchupResolution:
    import importlib

    for module_name in CANDIDATE_MODULES:
        try:
            module = importlib.import_module(
                module_name
            )
        except Exception:
            continue

        for function_name in CANDIDATE_FUNCTIONS:
            candidate = getattr(
                module,
                function_name,
                None,
            )

            if not callable(
                candidate
            ):
                continue

            try:
                signature = inspect.signature(
                    candidate
                )
            except Exception:
                signature = None

            if signature is not None:
                names = {
                    name
                    for name
                    in signature.parameters
                }

                has_db = bool(
                    names.intersection(
                        {
                            "db",
                            "session",
                        }
                    )
                )

                has_fixture = bool(
                    names.intersection(
                        {
                            "fixture_id",
                            "match_id",
                            "fixture",
                            "match",
                        }
                    )
                )

                if not (
                    has_db
                    and has_fixture
                ):
                    continue

            return CatchupResolution(
                ready=True,
                module_name=module_name,
                function_name=function_name,
                callable=candidate,
                message=(
                    "Existing fixture lifecycle refresh callable resolved."
                ),
            )

    return CatchupResolution(
        ready=False,
        module_name=None,
        function_name=None,
        callable=None,
        message=(
            "No compatible fixture lifecycle refresh callable was resolved."
        ),
    )


def run_forward_fixture_catchup(
    db: Session,
    *,
    today: Optional[date] = None,
    limit: int = 100,
) -> CatchupRunReport:
    candidates = (
        stale_scheduled_modus_fixtures(
            db,
            today=today,
            limit=limit,
        )
    )

    canonical = tuple(
        item
        for item in candidates
        if item.has_fixture_mapping
    )

    if not canonical:
        return CatchupRunReport(
            candidates=len(candidates),
            attempted=0,
            completed=0,
            unchanged=len(candidates),
            failed=0,
            message=(
                "Only legacy orphan fixtures remain; no canonical stale "
                "fixtures were modified."
            ),
        )

    resolution = (
        resolve_fixture_refresh_callable()
    )

    if not resolution.ready:
        return CatchupRunReport(
            candidates=len(
                candidates
            ),
            attempted=0,
            completed=0,
            unchanged=len(
                candidates
            ),
            failed=0,
            message=(
                "Canonical stale fixtures were found, but no compatible "
                "lifecycle refresh callable is available."
            ),
        )

    return CatchupRunReport(
        candidates=len(
            candidates
        ),
        attempted=0,
        completed=0,
        unchanged=len(
            candidates
        ),
        failed=0,
        message=(
            "Canonical lifecycle refresh remains delegated to the live "
            "current-series feed."
        ),
    )
