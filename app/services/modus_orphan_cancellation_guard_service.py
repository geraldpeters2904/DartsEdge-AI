from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models.canonical_data import (
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.match import Match
from app.services.modus_import_scope_service import (
    find_modus_import_scope_for_match,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


_STRICT_MODUS_MATCH_RE = re.compile(r"modus-match-(\d+)")


@dataclass(frozen=True)
class OrphanCancellationEligibility:
    fixture_id: int
    eligible: bool
    external_id: str | None
    reason: str


def check_orphan_cancellation_eligibility(
    db,
    group: StaleFixtureScopeGroup,
    fixture_id: int,
) -> OrphanCancellationEligibility:
    fixture_id = int(fixture_id)

    fixture = next(
        (
            item
            for item in group.fixtures
            if int(item.fixture_id) == fixture_id
        ),
        None,
    )

    if fixture is None:
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=None,
            reason="Fixture is not present in the supplied stale scope group.",
        )

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if match is None:
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=None,
            reason="Internal match does not exist.",
        )

    if str(match.status or "").strip().casefold() != "scheduled":
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=None,
            reason="Internal match is no longer scheduled.",
        )

    actual_scope = find_modus_import_scope_for_match(
        db,
        fixture_id,
    )

    if actual_scope != group.scope:
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=None,
            reason="Internal match does not belong to the exact MODUS scope.",
        )

    mappings = (
        db.query(ProviderEntityMapping)
        .filter(
            ProviderEntityMapping.provider == "modus-official",
            ProviderEntityMapping.entity_type == "fixture",
            ProviderEntityMapping.internal_id == fixture_id,
        )
        .order_by(ProviderEntityMapping.id.asc())
        .all()
    )

    strict_external_ids = tuple(
        dict.fromkeys(
            str(mapping.external_id or "").strip()
            for mapping in mappings
            if _STRICT_MODUS_MATCH_RE.fullmatch(
                str(mapping.external_id or "").strip()
            )
        )
    )

    if len(strict_external_ids) != 1:
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=None,
            reason=(
                "Fixture does not have exactly one strict modus-official "
                "fixture mapping."
            ),
        )

    external_id = strict_external_ids[0]

    raw_records = (
        db.query(RawIngestionRecord)
        .filter(
            RawIngestionRecord.provider == "modus-official",
            RawIngestionRecord.entity_type == "fixture",
            RawIngestionRecord.external_id == external_id,
        )
        .order_by(
            RawIngestionRecord.retrieved_at.asc(),
            RawIngestionRecord.id.asc(),
        )
        .all()
    )

    if not raw_records:
        return OrphanCancellationEligibility(
            fixture_id=fixture_id,
            eligible=False,
            external_id=external_id,
            reason="No raw MODUS observations exist for the mapped fixture.",
        )

    for record in raw_records:
        try:
            payload = json.loads(record.payload_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return OrphanCancellationEligibility(
                fixture_id=fixture_id,
                eligible=False,
                external_id=external_id,
                reason="A raw MODUS observation cannot be parsed safely.",
            )

        status = str(
            payload.get("status", "")
            if isinstance(payload, dict)
            else ""
        ).strip().casefold()

        if status == "completed":
            return OrphanCancellationEligibility(
                fixture_id=fixture_id,
                eligible=False,
                external_id=external_id,
                reason=(
                    "A completed raw MODUS observation exists for this "
                    "provisional fixture."
                ),
            )

    return OrphanCancellationEligibility(
        fixture_id=fixture_id,
        eligible=True,
        external_id=external_id,
        reason=(
            "Fixture is still scheduled in the exact MODUS scope, has one "
            "strict official mapping, and has no completed raw observation."
        ),
    )
