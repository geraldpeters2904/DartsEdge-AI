from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import date

from app.services.modus_import_scope_service import (
    ModusImportScope,
)
from app.services.modus_stale_reconciliation_execution_orchestrator import (
    execute_stale_reconciliation_results,
)
from app.services.modus_stale_reconciliation_plan_service import (
    StaleReconciliationPlan,
)
from app.services.modus_stale_reconciliation_service import (
    StaleScopeReconciliationResult,
)


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def __call__(
        self,
        db,
        *,
        mappings,
        workflow_service,
    ):
        self.calls.append(tuple(mappings))

        return FakeExecutionReport(
            attempted=len(mappings),
            completed=len(mappings),
            failed=0,
            failed_fixture_ids=(),
        )


@dataclass(frozen=True)
class FakeExecutionReport:
    attempted: int
    completed: int
    failed: int
    failed_fixture_ids: tuple


class ModusStaleReconciliationExecutionOrchestratorTests(
    unittest.TestCase
):

    def test_only_resolved_plans_are_executed(self):
        scope = ModusImportScope(
            series_id=26,
            week_id=196,
            group="Group B",
        )

        resolved = StaleScopeReconciliationResult(
            scope=scope,
            plan=StaleReconciliationPlan(
                resolved=True,
                mappings=(
                    (100, 19743),
                    (101, 19745),
                ),
                unmatched_fixture_ids=(),
            ),
            error=None,
        )

        unresolved = StaleScopeReconciliationResult(
            scope=scope,
            plan=StaleReconciliationPlan(
                resolved=False,
                mappings=(),
                unmatched_fixture_ids=(),
            ),
            error=None,
        )

        failed_fetch = StaleScopeReconciliationResult(
            scope=scope,
            plan=StaleReconciliationPlan(
                resolved=False,
                mappings=(),
                unmatched_fixture_ids=(),
            ),
            error="official page unavailable",
        )

        executor = FakeExecutor()

        report = execute_stale_reconciliation_results(
            object(),
            results=(
                resolved,
                unresolved,
                failed_fetch,
            ),
            workflow_service=object(),
            executor=executor,
        )

        self.assertEqual(
            executor.calls,
            [
                (
                    (100, 19743),
                    (101, 19745),
                )
            ],
        )

        self.assertEqual(report.scopes_seen, 3)
        self.assertEqual(report.scopes_executed, 1)
        self.assertEqual(report.scopes_deferred, 2)
        self.assertEqual(report.attempted, 2)
        self.assertEqual(report.completed, 2)
        self.assertEqual(report.failed, 0)


if __name__ == "__main__":
    unittest.main()
