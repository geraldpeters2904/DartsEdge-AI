from __future__ import annotations

from typing import Optional

from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.models.player import Player
from app.services.player_name_service import resolve_player_by_name
from app.schemas.canonical import CanonicalMatchResult
from app.services.canonical_data_service import map_entity


def find_match_by_external_id(
    *,
    db,
    provider: str,
    match_external_id: str,
) -> Optional[Match]:
    """Find an existing match using its provider fixture mapping."""

    mapping = (
        db.query(ProviderEntityMapping)
        .filter_by(
            provider=provider,
            entity_type="fixture",
            external_id=match_external_id,
        )
        .first()
    )

    if mapping is None:
        return None

    return (
        db.query(Match)
        .filter(Match.id == mapping.internal_id)
        .first()
    )


def player_name_for_external_id(
    *,
    db,
    provider: str,
    external_id: str,
    fallback: str,
) -> str:
    """Resolve a provider player ID to the canonical DartsEdge name."""

    mapping = (
        db.query(ProviderEntityMapping)
        .filter_by(
            provider=provider,
            entity_type="player",
            external_id=external_id,
        )
        .first()
    )

    if mapping is None:
        return fallback

    player = (
        db.query(Player)
        .filter(Player.id == mapping.internal_id)
        .first()
    )

    return player.name if player else fallback


def participant_name(
    *,
    external_id: str,
    result: CanonicalMatchResult,
    player_a_name: str,
    player_b_name: str,
) -> str:
    """Convert one result participant ID into its canonical player name."""

    if external_id == result.player_a_external_id:
        return player_a_name

    if external_id == result.player_b_external_id:
        return player_b_name

    raise ValueError(
        "Result participant identifier does not match either player."
    )


def optional_participant_name(
    *,
    external_id: Optional[str],
    result: CanonicalMatchResult,
    player_a_name: str,
    player_b_name: str,
) -> Optional[str]:
    """Resolve an optional result participant ID."""

    if external_id is None:
        return None

    return participant_name(
        external_id=external_id,
        result=result,
        player_a_name=player_a_name,
        player_b_name=player_b_name,
    )


def map_player_external_id(
    *,
    db,
    provider: str,
    external_id: str,
    player_name: str,
    competition_code: str,
) -> None:
    """Create or update a provider mapping for a canonical player ID."""

    player = resolve_player_by_name(
        db,
        player_name,
    )

    if player is None:
        raise ValueError(
            f"Canonical player was not created: {player_name}."
        )

    map_entity(
        db,
        provider,
        "player",
        external_id,
        player.id,
        competition_code,
    )