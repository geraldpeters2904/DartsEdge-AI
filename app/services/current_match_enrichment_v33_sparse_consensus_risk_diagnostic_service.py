from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.current_match_enrichment_v33_dual_low_history_risk_flag_service import (
    CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService,
)
from app.services.current_match_enrichment_v33_sparse_consensus_risk_state_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskStateService,
)


@dataclass(frozen=True)
class V33SparseConsensusRiskDiagnostic:
    model_version: str

    offset: int
    window_size: int

    probability_lower: float
    probability_upper: float

    history_threshold: int
    agreement_threshold: float

    segment_matches: int
    flagged_matches: int

    density: Optional[float]

    risk_state: str
    elevated: bool
    high: bool

    explanation: str


class CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService:
    """
    Read-only application-facing diagnostic for sparse-consensus
    regime risk.

    The service combines:

    - the existing sparse-consensus flag population calculation;
    - the evidence-backed density classifier.

    It does not change model probabilities, predictions or
    bet-selection behaviour.
    """

    def __init__(
        self,
        *,
        risk_flag_service=None,
        risk_state_service=None,
    ) -> None:
        self.risk_flag_service = (
            risk_flag_service
            or CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService()
        )

        self.risk_state_service = (
            risk_state_service
            or CurrentMatchEnrichmentV33SparseConsensusRiskStateService()
        )

    def analyse(
        self,
        db,
        *,
        offset: int,
        window_size: int = 1000,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        agreement_threshold: float = 100.0,
        competition_code: Optional[str] = "MODUS",
    ) -> V33SparseConsensusRiskDiagnostic:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero."
            )

        report = (
            self.risk_flag_service
            .analyse(
                db,
                offset=offset,
                limit=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                agreement_threshold=agreement_threshold,
                competition_code=competition_code,
            )
        )

        state = (
            self.risk_state_service
            .classify_counts(
                flagged_matches=report.flagged_matches,
                segment_matches=report.segment_matches,
            )
        )

        return V33SparseConsensusRiskDiagnostic(
            model_version=report.model_version,
            offset=offset,
            window_size=window_size,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_threshold=history_threshold,
            agreement_threshold=agreement_threshold,
            segment_matches=report.segment_matches,
            flagged_matches=report.flagged_matches,
            density=state.density,
            risk_state=state.state,
            elevated=state.elevated,
            high=state.high,
            explanation=state.explanation,
        )
