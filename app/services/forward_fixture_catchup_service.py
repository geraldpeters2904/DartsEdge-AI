from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match

from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)

from app.services.current_match_enrichment_workflow_service import (
    CurrentMatchEnrichmentWorkflowService,
)
from app.services.modus_completed_scope_fetcher_service import (
    ModusCompletedScopeFetcherService,
)
from app.services.modus_stale_scope_grouping_service import (
    group_stale_modus_fixtures_by_scope,
)
from app.services.modus_stale_reconciliation_service import (
    reconcile_stale_scope_groups,
)
from app.services.modus_stale_reconciliation_execution_orchestrator import (
    execute_stale_reconciliation_results,
)


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

    workflow_service=None,

    completed_scope_fetcher=None,

) -> CatchupRunReport:

    candidates = stale_scheduled_modus_fixtures(
        db,
        today=today,
        limit=limit,
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

    groups = group_stale_modus_fixtures_by_scope(
        db,
        today=today,
    )

    if not groups:
        return CatchupRunReport(
            candidates=len(candidates),
            attempted=0,
            completed=0,
            unchanged=len(candidates),
            failed=0,
            message=(
                f"Deferred {len(canonical)} canonical stale fixture(s); "
                "no recoverable MODUS import scope was available."
            ),
        )

    workflow = (
        workflow_service
        or CurrentMatchEnrichmentWorkflowService()
    )

    owns_fetcher = completed_scope_fetcher is None
    fetcher = (
        completed_scope_fetcher
        or ModusCompletedScopeFetcherService()
    )

    try:
        reconciliation_results = (
            reconcile_stale_scope_groups(
                groups,
                fetch_cards=fetcher.fetch,
            )
        )

        execution = (
            execute_stale_reconciliation_results(
                db,
                results=reconciliation_results,
                workflow_service=workflow,
            )
        )

    finally:
        if owns_fetcher:
            fetcher.close()

    unchanged = max(
        0,
        len(candidates) - execution.attempted,
    )

    return CatchupRunReport(
        candidates=len(candidates),
        attempted=execution.attempted,
        completed=execution.completed,
        unchanged=unchanged,
        failed=execution.failed,
        message=(
            "Sequence-aware MODUS stale fixture reconciliation "
            f"processed {execution.scopes_executed} scope(s); "
            f"{execution.scopes_deferred} scope(s) were deferred."
        ),
    )

