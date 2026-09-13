from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence, Tuple

from app.services.modus_reconciliation_plan_execution_service import (
    execute_modus_reconciliation_mappings,
)
from app.services.modus_stale_reconciliation_service import (
    StaleScopeReconciliationResult,
)


@dataclass(frozen=True)
class StaleReconciliationExecutionSummary:
    scopes_seen: int
    scopes_executed: int
    scopes_deferred: int
    attempted: int
    completed: int
    failed: int
    failed_fixture_ids: Tuple[int, ...]


def execute_stale_reconciliation_results(
    db,
    *,
    results: Sequence[StaleScopeReconciliationResult],
    workflow_service,
    executor: Callable = execute_modus_reconciliation_mappings,
) -> StaleReconciliationExecutionSummary:
    scopes_seen = 0
    scopes_executed = 0
    scopes_deferred = 0
    attempted = 0
    completed = 0
    failed = 0
    failed_fixture_ids = []

    for result in results:
        scopes_seen += 1

        if (
            result.error is not None
            or not result.plan.resolved
            or not result.plan.mappings
        ):
            scopes_deferred += 1
            continue

        report = executor(
            db,
            mappings=result.plan.mappings,
            workflow_service=workflow_service,
        )

        scopes_executed += 1
        attempted += int(report.attempted)
        completed += int(report.completed)
        failed += int(report.failed)

        failed_fixture_ids.extend(
            int(fixture_id)
            for fixture_id in report.failed_fixture_ids
        )

    return StaleReconciliationExecutionSummary(
        scopes_seen=scopes_seen,
        scopes_executed=scopes_executed,
        scopes_deferred=scopes_deferred,
        attempted=attempted,
        completed=completed,
        failed=failed,
        failed_fixture_ids=tuple(
            failed_fixture_ids
        ),
    )
