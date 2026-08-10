from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.providers.adapters.modus_official.identifiers import (
    modus_match_external_id,
    modus_player_external_id,
)
from app.schemas.canonical import CanonicalPlayerMatchStatistics
from app.services.current_match_enrichment_detail_service import (
    CurrentMatchEnrichmentDetailResult,
)
from app.services.modus_canonical_builder import (
    ModusCanonicalBuilder,
)


@dataclass(frozen=True)
class CurrentMatchEnrichmentStatisticsResult:
    internal_match_id: int
    modus_match_id: int
    match_external_id: str
    statistics: tuple[
        CanonicalPlayerMatchStatistics,
        CanonicalPlayerMatchStatistics,
    ]
    status: str
    message: str


class CurrentMatchEnrichmentStatisticsService:
    """
    Convert one validated MODUS match detail into canonical statistics.

    This service is read-only. It does not commit statistics to the warehouse.
    """

    def __init__(
        self,
        *,
        canonical_builder: ModusCanonicalBuilder | None = None,
    ) -> None:
        self.canonical_builder = (
            canonical_builder or ModusCanonicalBuilder()
        )

    def build(
        self,
        detail_result: CurrentMatchEnrichmentDetailResult,
        *,
        retrieved_at: datetime | None = None,
    ) -> CurrentMatchEnrichmentStatisticsResult:
        if detail_result.status != "validated":
            raise ValueError(
                "Only validated enrichment detail can be converted."
            )

        detail = detail_result.detail
        modus_match_id = int(
            detail_result.modus_match_id
        )

        if int(detail.match_id) != modus_match_id:
            raise ValueError(
                "Parsed MODUS detail match ID does not match "
                "the validated enrichment match ID."
            )

        match_external_id = (
            modus_match_external_id(
                modus_match_id
            )
        )

        player_a_external_id = (
            modus_player_external_id(
                detail.player_a_name
            )
        )
        player_b_external_id = (
            modus_player_external_id(
                detail.player_b_name
            )
        )

        observed_at = (
            retrieved_at or datetime.utcnow()
        )

        stats_a = (
            self.canonical_builder
            ._statistics_record(
                match_id=modus_match_id,
                match_external_id=match_external_id,
                player_external_id=player_a_external_id,
                player_stats=detail.player_a_stats,
                legs_won=int(
                    detail.player_a_legs
                ),
                legs_lost=int(
                    detail.player_b_legs
                ),
                retrieved_at=observed_at,
            )
        )

        stats_b = (
            self.canonical_builder
            ._statistics_record(
                match_id=modus_match_id,
                match_external_id=match_external_id,
                player_external_id=player_b_external_id,
                player_stats=detail.player_b_stats,
                legs_won=int(
                    detail.player_b_legs
                ),
                legs_lost=int(
                    detail.player_a_legs
                ),
                retrieved_at=observed_at,
            )
        )

        return CurrentMatchEnrichmentStatisticsResult(
            internal_match_id=int(
                detail_result.internal_match_id
            ),
            modus_match_id=modus_match_id,
            match_external_id=match_external_id,
            statistics=(
                stats_a,
                stats_b,
            ),
            status="canonicalized",
            message=(
                "Validated MODUS match detail converted into "
                "two canonical player-match statistics records."
            ),
        )
