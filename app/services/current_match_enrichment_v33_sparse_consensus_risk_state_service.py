from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class V33SparseConsensusRiskState:
    """
    Read-only sparse-consensus regime classification.

    The state describes the current density regime only.
    It does not alter predictions or reject bets.
    """

    density: Optional[float]
    state: str
    elevated: bool
    high: bool
    explanation: str


class CurrentMatchEnrichmentV33SparseConsensusRiskStateService:
    """
    Convert sparse-consensus density into a reusable risk state.

    Evidence-backed thresholds:

        NORMAL
            density <= 1%

        ELEVATED_SPARSE_CONSENSUS_RISK
            density > 1% and <= 3%

        HIGH_SPARSE_CONSENSUS_RISK
            density > 3%

    A missing density is classified as UNKNOWN rather than
    silently treated as normal.

    This service is classification-only. It does not modify
    transparent-v3.3 or bet-selection behaviour.
    """

    NORMAL = "NORMAL"

    ELEVATED = (
        "ELEVATED_SPARSE_CONSENSUS_RISK"
    )

    HIGH = (
        "HIGH_SPARSE_CONSENSUS_RISK"
    )

    UNKNOWN = "UNKNOWN"

    ELEVATED_THRESHOLD = 1.0
    HIGH_THRESHOLD = 3.0

    def classify(
        self,
        density: Optional[float],
    ) -> V33SparseConsensusRiskState:
        if density is None:
            return V33SparseConsensusRiskState(
                density=None,
                state=self.UNKNOWN,
                elevated=False,
                high=False,
                explanation=(
                    "Sparse-consensus density is unavailable, "
                    "so the regime risk state cannot be determined."
                ),
            )

        density = float(density)

        if density < 0.0:
            raise ValueError(
                "density cannot be negative."
            )

        if density > self.HIGH_THRESHOLD:
            return V33SparseConsensusRiskState(
                density=density,
                state=self.HIGH,
                elevated=True,
                high=True,
                explanation=(
                    "Sparse-consensus density is above 3%, "
                    "placing the current regime in the high-risk band."
                ),
            )

        if density > self.ELEVATED_THRESHOLD:
            return V33SparseConsensusRiskState(
                density=density,
                state=self.ELEVATED,
                elevated=True,
                high=False,
                explanation=(
                    "Sparse-consensus density is above 1%, "
                    "placing the current regime in the "
                    "elevated-risk band."
                ),
            )

        return V33SparseConsensusRiskState(
            density=density,
            state=self.NORMAL,
            elevated=False,
            high=False,
            explanation=(
                "Sparse-consensus density is at or below 1%, "
                "so the current regime is classified as normal."
            ),
        )

    def classify_counts(
        self,
        *,
        flagged_matches: int,
        segment_matches: int,
    ) -> V33SparseConsensusRiskState:
        if flagged_matches < 0:
            raise ValueError(
                "flagged_matches cannot be negative."
            )

        if segment_matches < 0:
            raise ValueError(
                "segment_matches cannot be negative."
            )

        if flagged_matches > segment_matches:
            raise ValueError(
                "flagged_matches cannot exceed segment_matches."
            )

        if segment_matches == 0:
            return self.classify(None)

        density = round(
            flagged_matches
            / segment_matches
            * 100.0,
            6,
        )

        return self.classify(
            density
        )
