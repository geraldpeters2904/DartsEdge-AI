from __future__ import annotations

from typing import Callable, Sequence, Tuple

from app.services.modus_anchor_reconciliation_service import (
    build_anchor_aware_stale_reconciliation_plan,
    discover_verified_sequence_anchors,
)
from app.services.modus_import_scope_service import (
    ModusImportScope,
)
from app.services.modus_stale_reconciliation_plan_service import (
    StaleReconciliationPlan,
    build_stale_reconciliation_plan,
)
from app.services.modus_stale_reconciliation_service import (
    StaleScopeReconciliationResult,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


def _empty_plan() -> StaleReconciliationPlan:
    return StaleReconciliationPlan(
        resolved=False,
        mappings=(),
        unmatched_fixture_ids=(),
    )


def reconcile_stale_scope_groups_with_verified_anchors(
    db,
    groups: Sequence[StaleFixtureScopeGroup],
    *,
    fetch_cards: Callable[[ModusImportScope], Sequence[object]],
) -> Tuple[StaleScopeReconciliationResult, ...]:
    results = []

    for group in groups:
        try:
            completed_cards = tuple(fetch_cards(group.scope))

            plan = build_stale_reconciliation_plan(
                group,
                completed_cards,
            )

            if not plan.resolved:
                anchors = discover_verified_sequence_anchors(
                    db,
                    group,
                    completed_cards,
                )

                plan = build_anchor_aware_stale_reconciliation_plan(
                    group,
                    completed_cards,
                    anchors=anchors,
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
