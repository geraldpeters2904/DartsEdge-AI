from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

from app.services.modus_import_scope_service import (
    ModusImportScope,
)
from app.services.modus_stale_reconciliation_plan_service import (
    StaleReconciliationPlan,
    build_stale_reconciliation_plan,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


@dataclass(frozen=True)
class StaleScopeReconciliationResult:
    scope: ModusImportScope
    plan: StaleReconciliationPlan
    error: Optional[str] = None


def _empty_plan() -> StaleReconciliationPlan:
    return StaleReconciliationPlan(
        resolved=False,
        mappings=(),
        unmatched_fixture_ids=(),
    )


def reconcile_stale_scope_groups(
    groups: Sequence[StaleFixtureScopeGroup],
    *,
    fetch_cards: Callable[[ModusImportScope], Sequence[object]],
) -> Tuple[StaleScopeReconciliationResult, ...]:
    results = []

    for group in groups:
        try:
            completed_cards = fetch_cards(group.scope)

            plan = build_stale_reconciliation_plan(
                group,
                completed_cards,
            )

            results.append(
                StaleScopeReconciliationResult(
                    scope=group.scope,
                    plan=plan,
                    error=None,
                )
            )

        except Exception as exc:
            results.append(
                StaleScopeReconciliationResult(
                    scope=group.scope,
                    plan=_empty_plan(),
                    error=str(exc),
                )
            )

    return tuple(results)
