from __future__ import annotations

from app.models.canonical_data import (
    ProviderEntityMapping,
)


def replace_with_verified_modus_mapping(
    db,
    *,
    fixture_id: int,
    real_match_id: int,
) -> ProviderEntityMapping:
    fixture_id = int(fixture_id)
    real_match_id = int(real_match_id)

    verified_external_id = (
        f"modus-match-{real_match_id}"
    )

    existing_verified = (
        db.query(ProviderEntityMapping)
        .filter_by(
            provider="modus-official",
            entity_type="fixture",
            external_id=verified_external_id,
        )
        .first()
    )

    if (
        existing_verified is not None
        and int(existing_verified.internal_id)
        != fixture_id
    ):
        raise ValueError(
            "Verified MODUS match ID "
            f"{real_match_id} is already mapped "
            f"to fixture {existing_verified.internal_id}."
        )

    target_mappings = (
        db.query(ProviderEntityMapping)
        .filter_by(
            provider="modus-official",
            entity_type="fixture",
            internal_id=fixture_id,
        )
        .all()
    )

    if existing_verified is not None:
        for mapping in target_mappings:
            if mapping.id != existing_verified.id:
                db.delete(mapping)

        return existing_verified

    for mapping in target_mappings:
        db.delete(mapping)

    verified_mapping = ProviderEntityMapping(
        provider="modus-official",
        entity_type="fixture",
        external_id=verified_external_id,
        internal_id=fixture_id,
        competition_code="MODUS",
    )

    db.add(verified_mapping)
    db.flush()

    return verified_mapping
