from __future__ import annotations

from dataclasses import dataclass

from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.player_career_profile_cache_service import (
    PlayerCareerProfileCacheService,
)


@dataclass(frozen=True)
class CurrentMatchEnrichmentProfileRefreshResult:
    internal_match_id: int
    player_ids: tuple[int, ...]
    refreshed_count: int
    status: str
    message: str


class CurrentMatchEnrichmentProfileRefreshService:
    """
    Refresh derived career profiles for players affected by enrichment.

    PlayerMatchPerformance remains the source of truth. Career profiles are
    derived cache data and can be rebuilt safely.
    """

    def __init__(
        self,
        *,
        profile_cache_service=None,
    ) -> None:
        self.profile_cache_service = (
            profile_cache_service
            or PlayerCareerProfileCacheService()
        )

    def refresh(
        self,
        db,
        *,
        internal_match_id: int,
    ) -> CurrentMatchEnrichmentProfileRefreshResult:
        player_ids = tuple(
            sorted(
                {
                    int(row[0])
                    for row in (
                        db.query(
                            PlayerMatchPerformance.player_id
                        )
                        .filter(
                            PlayerMatchPerformance.match_id
                            == int(internal_match_id)
                        )
                        .all()
                    )
                }
            )
        )

        if len(player_ids) != 2:
            raise ValueError(
                "Current-match enrichment expected exactly two "
                "player performance records before profile refresh."
            )

        profiles = (
            self.profile_cache_service
            .refresh_players(
                db,
                player_ids=player_ids,
            )
        )

        return CurrentMatchEnrichmentProfileRefreshResult(
            internal_match_id=int(
                internal_match_id
            ),
            player_ids=player_ids,
            refreshed_count=len(profiles),
            status="refreshed",
            message=(
                "Career profiles refreshed for both players "
                "using the newly enriched performance data."
            ),
        )
