from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.player import Player
from app.models.player_stats import PlayerStats
from app.models.player_career_profile import (
    PlayerCareerProfile,
)
from app.services.player_career_profile_cache_service import (
    ALL_COMPETITIONS,
    PlayerCareerProfileCacheService,
)
from app.services.rating_service import dartsedge_rating


profile_cache_service = PlayerCareerProfileCacheService()


def get_player_profile(
    db: Session,
    player_name: str,
) -> Optional[dict]:
    """
    Return the compatibility player-profile payload from the modern cache.

    The public keys used by Player Intelligence remain available while
    richer warehouse-derived statistics are included for new consumers.
    """

    player = (
        db.query(Player)
        .filter(Player.name == player_name)
        .one_or_none()
    )

    if player is None:
        return None

    profile = (
        db.query(PlayerCareerProfile)
        .filter(
            PlayerCareerProfile.player_id == player.id,
            PlayerCareerProfile.competition_code
            == ALL_COMPETITIONS,
        )
        .one_or_none()
    )

    if profile is None:
        profile = profile_cache_service.refresh_player(
            db,
            player_id=player.id,
        )

    recent_form = (
        profile_cache_service.recent_form(profile)
    )


    legacy_stats = None

    if int(profile.matches_played or 0) == 0:
        legacy_stats = (
            db.query(PlayerStats)
            .filter(PlayerStats.player_id == player.id)
            .one_or_none()
        )

    matches = (
        int(legacy_stats.matches or 0)
        if legacy_stats is not None
        else int(profile.matches_played or 0)
    )

    wins = (
        int(legacy_stats.wins or 0)
        if legacy_stats is not None
        else int(profile.wins or 0)
    )

    losses = (
        int(legacy_stats.losses or 0)
        if legacy_stats is not None
        else int(profile.losses or 0)
    )

    legs_won = (
        int(legacy_stats.legs_won or 0)
        if legacy_stats is not None
        else int(profile.legs_won or 0)
    )

    legs_lost = (
        int(legacy_stats.legs_lost or 0)
        if legacy_stats is not None
        else int(profile.legs_lost or 0)
    )

    win_pct = (
        (wins / matches * 100.0)
        if legacy_stats is not None and matches > 0
        else profile.win_percentage
    )

    payload = {
        "name": player.name,
        "elo": player.elo,
        "average": (
            profile.average_three_dart_average
            if profile.average_three_dart_average is not None
            else player.average
        ),
        "checkout": (
            profile.calculated_checkout_percentage
            if profile.calculated_checkout_percentage is not None
            else player.checkout
        ),
        "matches": matches,
        "wins": wins,
        "losses": losses,
        "win_pct": win_pct,
        "legs_won": legs_won,
        "legs_lost": legs_lost,
        "leg_difference": legs_won - legs_lost,
        "first_nine_average": (
            profile.average_first_nine_average
        ),
        "scores_100_plus": profile.scores_100_plus,
        "scores_140_plus": profile.scores_140_plus,
        "scores_180": profile.scores_180,
        "maximums_per_match": profile.maximums_per_match,
        "checkout_attempts": profile.checkout_attempts,
        "checkouts_completed": profile.checkouts_completed,
        "highest_checkout": profile.highest_checkout,
        "recent_form": recent_form,
        "form": {
            "expected": profile.maximums_per_match,
            "recent": recent_form,
        },
        "confidence": min(
            95,
            40 + matches,
        ),
        "first_match_date": (
            profile.first_match_date.isoformat()
            if profile.first_match_date
            else None
        ),
        "latest_match_date": (
            profile.latest_match_date.isoformat()
            if profile.latest_match_date
            else None
        ),
        "profile_refreshed_at": (
            profile.refreshed_at.isoformat()
            if profile.refreshed_at
            else None
        ),
    }

    payload["dartsedge_rating"] = (
        dartsedge_rating(payload)
    )

    return payload
