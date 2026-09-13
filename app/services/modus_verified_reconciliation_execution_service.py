from __future__ import annotations

from app.models.match import Match
from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)
from app.services.modus_verified_mapping_service import (
    replace_with_verified_modus_mapping,
)


def execute_verified_modus_reconciliation(
    db,
    *,
    fixture_id: int,
    real_match_id: int,
    workflow_service,
):
    fixture_id = int(fixture_id)
    real_match_id = int(real_match_id)

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .one_or_none()
    )

    if match is None:
        raise ValueError(
            f"Fixture {fixture_id} does not exist."
        )

    if str(match.status).casefold() != "scheduled":
        raise ValueError(
            f"Fixture {fixture_id} is not scheduled."
        )

    replace_with_verified_modus_mapping(
        db,
        fixture_id=fixture_id,
        real_match_id=real_match_id,
    )

    candidate = EnrichmentCandidate(
        internal_match_id=fixture_id,
        fixture_date=match.date,
        player_a=match.player_a,
        player_b=match.player_b,
        stage=match.stage,
        resolved_modus_match_id=real_match_id,
        candidate_modus_match_ids=(real_match_id,),
        status="resolved",
        message=(
            "Resolved by deterministic MODUS "
            "sequence reconciliation."
        ),
    )

    return workflow_service.run(
        db,
        candidate,
    )
