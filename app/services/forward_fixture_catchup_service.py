from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models.match import Match


@dataclass(frozen=True)
class CatchupCandidate:
    fixture_id: int
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    days_stale: int


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

            # Accept only functions that can plausibly receive a DB session
            # and fixture/match identifier. We do not guess beyond that.
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


def _call_refresh(
    fn: Callable[..., Any],
    *,
    db: Session,
    fixture: Match,
):
    signature = inspect.signature(
        fn
    )

    parameters = (
        signature.parameters
    )

    kwargs = {}

    if "db" in parameters:
        kwargs["db"] = db
    elif "session" in parameters:
        kwargs["session"] = db

    if "fixture_id" in parameters:
        kwargs["fixture_id"] = fixture.id
    elif "match_id" in parameters:
        kwargs["match_id"] = fixture.id
    elif "fixture" in parameters:
        kwargs["fixture"] = fixture
    elif "match" in parameters:
        kwargs["match"] = fixture

    return fn(
        **kwargs
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

    resolution = (
        resolve_fixture_refresh_callable()
    )

    if not candidates:
        return CatchupRunReport(
            candidates=0,
            attempted=0,
            completed=0,
            unchanged=0,
            failed=0,
            message=(
                "No stale scheduled MODUS fixtures require catch-up."
            ),
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
                "Stale fixtures found, but no compatible lifecycle "
                "refresh callable is available. Nothing was modified."
            ),
        )

    completed = 0
    unchanged = 0
    failed = 0

    for item in candidates:
        fixture = (
            db.query(Match)
            .filter(
                Match.id
                == item.fixture_id
            )
            .first()
        )

        if fixture is None:
            failed += 1
            continue

        before = str(
            fixture.status
            or ""
        )

        try:
            _call_refresh(
                resolution.callable,
                db=db,
                fixture=fixture,
            )

            try:
                db.refresh(
                    fixture
                )
            except Exception:
                pass

            after = str(
                fixture.status
                or ""
            )

            if (
                before != "completed"
                and after == "completed"
            ):
                completed += 1
            else:
                unchanged += 1

        except Exception:
            failed += 1

    return CatchupRunReport(
        candidates=len(
            candidates
        ),
        attempted=len(
            candidates
        ),
        completed=completed,
        unchanged=unchanged,
        failed=failed,
        message=(
            f"Forward catch-up checked {len(candidates)} stale fixture(s): "
            f"{completed} completed, {unchanged} unchanged, {failed} failed."
        ),
    )
