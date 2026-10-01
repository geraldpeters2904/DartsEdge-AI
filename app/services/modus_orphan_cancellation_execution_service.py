from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from app.models.canonical_data import DataProvenance
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.schemas.canonical.common import (
    MatchStatus,
    RecordConfidence,
)
from app.services.modus_orphan_cancellation_guard_service import (
    check_orphan_cancellation_eligibility,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


_RECONCILIATION_PROVIDER = "modus-reconciliation"


@dataclass(frozen=True)
class OrphanCancellationExecutionResult:
    fixture_id: int
    external_id: str
    batch_id: int
    previous_status: str
    status: str


def execute_derived_orphan_cancellation(
    db,
    *,
    group: StaleFixtureScopeGroup,
    fixture_id: int,
    structural_reason: str,
) -> OrphanCancellationExecutionResult:
    fixture_id = int(fixture_id)

    eligibility = check_orphan_cancellation_eligibility(
        db,
        group,
        fixture_id,
    )

    if not eligibility.eligible:
        raise ValueError(
            "Fixture is not eligible for derived orphan cancellation: "
            f"{eligibility.reason}"
        )

    if not eligibility.external_id:
        raise ValueError(
            "Eligible orphan cancellation is missing its official external ID."
        )

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .one_or_none()
    )

    if match is None:
        raise ValueError(
            f"Fixture {fixture_id} does not exist."
        )

    previous_status = str(match.status or "")

    if previous_status.casefold() != MatchStatus.SCHEDULED.value:
        raise ValueError(
            f"Fixture {fixture_id} is no longer scheduled."
        )

    batch = HistoricalImportBatch(
        batch_uuid=str(uuid.uuid4()),
        filename=(
            "derived-modus-orphan-cancellation-"
            f"{fixture_id}.json"
        ),
        provider=_RECONCILIATION_PROVIDER,
        competition_code="MODUS",
        status="importing",
        received_rows=1,
        created_matches=0,
        duplicate_matches=0,
        rejected_rows=0,
        created_players=0,
    )
    db.add(batch)
    db.flush()

    match.status = MatchStatus.CANCELLED.value

    detail = {
        "operation": "derived_orphan_cancellation",
        "confidence": RecordConfidence.DERIVED.value,
        "previous": {
            "status": previous_status,
        },
        "current": {
            "status": MatchStatus.CANCELLED.value,
        },
        "evidence": {
            "scope": {
                "series_id": int(group.scope.series_id),
                "week_id": int(group.scope.week_id),
                "group": str(group.scope.group),
            },
            "official_external_id": eligibility.external_id,
            "structural_reason": str(structural_reason),
            "guard_reason": eligibility.reason,
        },
    }

    db.add(
        HistoricalImportItem(
            batch_id=batch.id,
            entity_type="fixture",
            internal_id=fixture_id,
            external_id=eligibility.external_id,
            action="updated",
            created_by_batch=False,
            detail=json.dumps(
                detail,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    )

    db.add(
        DataProvenance(
            entity_type="fixture",
            internal_id=fixture_id,
            field_name="status",
            provider=_RECONCILIATION_PROVIDER,
            external_id=eligibility.external_id,
            confidence=RecordConfidence.DERIVED.value,
        )
    )

    batch.status = "imported"

    db.flush()

    return OrphanCancellationExecutionResult(
        fixture_id=fixture_id,
        external_id=eligibility.external_id,
        batch_id=int(batch.id),
        previous_status=previous_status,
        status=MatchStatus.CANCELLED.value,
    )
