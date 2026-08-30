from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.providers.adapters.modus_official.identifiers import (
    modus_match_external_id,
    modus_player_external_id,
    modus_source_external_id,
)
from app.schemas.canonical import (
    CanonicalMatchResult,
    CanonicalPlayerMatchStatistics,
    CompetitionCode,
    RecordConfidence,
    SourceReference,
)
from app.services.current_match_enrichment_detail_service import (
    CurrentMatchEnrichmentDetailResult,
)
from app.services.modus_canonical_builder import (
    ModusCanonicalBuilder,
)


PROVIDER = "modus-official"


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
    result: CanonicalMatchResult | None = None


class CurrentMatchEnrichmentStatisticsService:
    """
    Convert one validated MODUS match detail into a canonical result plus
    canonical player-match statistics.

    This service is read-only. Persistence is owned by the enrichment
    persistence service.
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
        modus_match_id = int(detail_result.modus_match_id)

        if int(detail.match_id) != modus_match_id:
            raise ValueError(
                "Parsed MODUS detail match ID does not match "
                "the validated enrichment match ID."
            )

        player_a_legs = int(detail.player_a_legs)
        player_b_legs = int(detail.player_b_legs)

        if player_a_legs == player_b_legs:
            raise ValueError(
                "Completed MODUS enrichment detail cannot be a draw."
            )

        match_external_id = modus_match_external_id(
            modus_match_id
        )
        player_a_external_id = modus_player_external_id(
            detail.player_a_name
        )
        player_b_external_id = modus_player_external_id(
            detail.player_b_name
        )
        winner_external_id = (
            player_a_external_id
            if player_a_legs > player_b_legs
            else player_b_external_id
        )

        observed_at = retrieved_at or datetime.utcnow()
        completed_at = getattr(detail, "played_at", None)
        if completed_at is None:
            completed_at = observed_at

        result_source = SourceReference(
            provider=PROVIDER,
            external_id=modus_source_external_id(
                "result",
                match_id=modus_match_id,
            ),
            retrieved_at=observed_at,
            competition_code=CompetitionCode.MODUS,
            confidence=RecordConfidence.VERIFIED,
        )

        canonical_result = CanonicalMatchResult(
            match_external_id=match_external_id,
            player_a_external_id=player_a_external_id,
            player_b_external_id=player_b_external_id,
            winner_external_id=winner_external_id,
            player_a_legs=player_a_legs,
            player_b_legs=player_b_legs,
            completed_at=completed_at,
            source=result_source,
        )

        stats_a = self.canonical_builder._statistics_record(
            match_id=modus_match_id,
            match_external_id=match_external_id,
            player_external_id=player_a_external_id,
            player_stats=detail.player_a_stats,
            legs_won=player_a_legs,
            legs_lost=player_b_legs,
            retrieved_at=observed_at,
        )
        stats_b = self.canonical_builder._statistics_record(
            match_id=modus_match_id,
            match_external_id=match_external_id,
            player_external_id=player_b_external_id,
            player_stats=detail.player_b_stats,
            legs_won=player_b_legs,
            legs_lost=player_a_legs,
            retrieved_at=observed_at,
        )

        return CurrentMatchEnrichmentStatisticsResult(
            internal_match_id=int(
                detail_result.internal_match_id
            ),
            modus_match_id=modus_match_id,
            match_external_id=match_external_id,
            statistics=(stats_a, stats_b),
            status="canonicalized",
            message=(
                "Validated MODUS match detail converted into one "
                "canonical result and two canonical player-match "
                "statistics records."
            ),
            result=canonical_result,
        )
