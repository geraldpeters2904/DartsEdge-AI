from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from app.services.modus_orphan_cancellation_execution_service import (
    OrphanCancellationExecutionResult,
    execute_derived_orphan_cancellation,
)
from app.services.modus_orphan_cancellation_guard_service import (
    check_orphan_cancellation_eligibility,
)
from app.services.modus_orphan_cancellation_plan_service import (
    build_orphan_cancellation_plan,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


@dataclass(frozen=True)
class OrphanCancellationOrchestrationResult:
    attempted: int
    cancelled: int
    deferred: int
    executions: Tuple[OrphanCancellationExecutionResult, ...]
    errors: Tuple[str, ...]


def execute_unmatched_orphan_cancellations(
    db,
    *,
    group: StaleFixtureScopeGroup,
    unmatched_fixture_ids: Sequence[int],
    completed_cards: Sequence[object],
) -> OrphanCancellationOrchestrationResult:
    unmatched_ids = {
        int(fixture_id)
        for fixture_id in unmatched_fixture_ids
    }

    if not unmatched_ids:
        return OrphanCancellationOrchestrationResult(
            attempted=0,
            cancelled=0,
            deferred=0,
            executions=(),
            errors=(),
        )

    reduced_group = StaleFixtureScopeGroup(
        scope=group.scope,
        fixtures=tuple(
            fixture
            for fixture in group.fixtures
            if int(fixture.fixture_id) in unmatched_ids
        ),
    )

    if not reduced_group.fixtures:
        return OrphanCancellationOrchestrationResult(
            attempted=0,
            cancelled=0,
            deferred=len(unmatched_ids),
            executions=(),
            errors=(
                "No unmatched fixture IDs were present in the supplied stale scope group.",
            ),
        )

    plan = build_orphan_cancellation_plan(
        reduced_group,
        completed_cards,
    )

    if not plan.resolved:
        return OrphanCancellationOrchestrationResult(
            attempted=0,
            cancelled=0,
            deferred=len(reduced_group.fixtures),
            executions=(),
            errors=(),
        )

    executions = []
    errors = []

    for fixture_id in plan.fixture_ids:
        eligibility = check_orphan_cancellation_eligibility(
            db,
            reduced_group,
            fixture_id,
        )

        if not eligibility.eligible:
            errors.append(
                f"Fixture {fixture_id}: {eligibility.reason}"
            )
            continue

        try:
            execution = execute_derived_orphan_cancellation(
                db,
                group=reduced_group,
                fixture_id=fixture_id,
                structural_reason=plan.reason,
            )
        except Exception as exc:
            errors.append(
                f"Fixture {fixture_id}: {exc}"
            )
            continue

        executions.append(execution)

    attempted = len(plan.fixture_ids)
    cancelled = len(executions)

    return OrphanCancellationOrchestrationResult(
        attempted=attempted,
        cancelled=cancelled,
        deferred=max(
            0,
            len(reduced_group.fixtures) - cancelled,
        ),
        executions=tuple(executions),
        errors=tuple(errors),
    )
