from __future__ import annotations

from dataclasses import dataclass

from app.services.current_match_enrichment_detail_service import (
    CurrentMatchEnrichmentDetailService,
)
from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)
from app.services.current_match_enrichment_persistence_service import (
    CurrentMatchEnrichmentPersistenceService,
)
from app.services.current_match_enrichment_profile_refresh_service import (
    CurrentMatchEnrichmentProfileRefreshService,
)
from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsService,
)


@dataclass(frozen=True)
class CurrentMatchEnrichmentWorkflowResult:
    internal_match_id: int
    modus_match_id: int
    detail_status: str
    statistics_status: str
    persistence_status: str
    profile_refresh_status: str
    refreshed_profiles: int
    batch_id: int
    status: str
    message: str


class CurrentMatchEnrichmentWorkflowService:
    """
    Execute one explicitly selected current-match enrichment.

    Discovery remains read-only. This workflow must be called deliberately
    with a resolved candidate before any warehouse write can occur.
    """

    def __init__(
        self,
        *,
        detail_service=None,
        statistics_service=None,
        persistence_service=None,
        profile_refresh_service=None,
    ) -> None:
        self.detail_service = (
            detail_service
            or CurrentMatchEnrichmentDetailService()
        )
        self.statistics_service = (
            statistics_service
            or CurrentMatchEnrichmentStatisticsService()
        )
        self.persistence_service = (
            persistence_service
            or CurrentMatchEnrichmentPersistenceService()
        )
        self.profile_refresh_service = (
            profile_refresh_service
            or CurrentMatchEnrichmentProfileRefreshService()
        )

    def run(
        self,
        db,
        candidate: EnrichmentCandidate,
        *,
        timeout_seconds: float = 30.0,
    ) -> CurrentMatchEnrichmentWorkflowResult:
        if candidate.status != "resolved":
            raise ValueError(
                "Only resolved enrichment candidates "
                "can enter the enrichment workflow."
            )

        detail = self.detail_service.fetch(
            candidate,
            timeout_seconds=timeout_seconds,
        )

        statistics = self.statistics_service.build(
            detail
        )

        persisted = self.persistence_service.persist(
            db,
            statistics,
        )

        profile_refresh = (
            self.profile_refresh_service.refresh(
                db,
                internal_match_id=(
                    candidate.internal_match_id
                ),
            )
        )

        return CurrentMatchEnrichmentWorkflowResult(
            internal_match_id=int(
                candidate.internal_match_id
            ),
            modus_match_id=int(
                persisted.modus_match_id
            ),
            detail_status=detail.status,
            statistics_status=statistics.status,
            persistence_status=persisted.status,
            profile_refresh_status=(
                profile_refresh.status
            ),
            refreshed_profiles=int(
                profile_refresh.refreshed_count
            ),
            batch_id=int(
                persisted.batch_id
            ),
            status="completed",
            message=(
                "Current MODUS match enrichment completed "
                "through validated detail, canonical statistics "
                "and immutable persistence."
            ),
        )
