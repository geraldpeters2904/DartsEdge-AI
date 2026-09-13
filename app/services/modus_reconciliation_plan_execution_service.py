from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from app.services.modus_verified_reconciliation_execution_service import (
    execute_verified_modus_reconciliation,
)


@dataclass(frozen=True)
class ModusReconciliationExecutionReport:
    attempted: int
    completed: int
    failed: int
    failed_fixture_ids: Tuple[int, ...]


def execute_modus_reconciliation_mappings(
    db,
    *,
    mappings: Sequence[Tuple[int, int]],
    workflow_service,
) -> ModusReconciliationExecutionReport:
    attempted = 0
    completed = 0
    failed_fixture_ids = []

    for fixture_id, real_match_id in mappings:
        attempted += 1

        try:
            with db.begin_nested():
                execute_verified_modus_reconciliation(
                    db,
                    fixture_id=int(fixture_id),
                    real_match_id=int(real_match_id),
                    workflow_service=workflow_service,
                )

                db.flush()

            completed += 1

        except Exception:
            failed_fixture_ids.append(
                int(fixture_id)
            )

    return ModusReconciliationExecutionReport(
        attempted=attempted,
        completed=completed,
        failed=len(failed_fixture_ids),
        failed_fixture_ids=tuple(
            failed_fixture_ids
        ),
    )
