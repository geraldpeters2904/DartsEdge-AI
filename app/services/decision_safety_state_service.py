from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DecisionSafetyState:
    state: str
    caution: bool
    high_caution: bool
    trust_score: Optional[float]
    sparse_consensus_risk_state: str
    explanation: str


class DecisionSafetyStateService:
    """
    Read-only decision-safety classification.

    Combines historical model trust with the current
    sparse-consensus regime.

    This service does not alter:
    - prediction probabilities;
    - Decision Intelligence scores;
    - recommendations;
    - stakes;
    - opportunity ranking.
    """

    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    HIGH_CAUTION = "HIGH_CAUTION"
    UNKNOWN = "UNKNOWN"

    HIGH_RISK = (
        "HIGH_SPARSE_CONSENSUS_RISK"
    )

    ELEVATED_RISK = (
        "ELEVATED_SPARSE_CONSENSUS_RISK"
    )

    NORMAL_RISK = "NORMAL"
    UNKNOWN_RISK = "UNKNOWN"

    def classify(
        self,
        *,
        trust_score: Optional[float],
        sparse_consensus_risk_state: str,
    ) -> DecisionSafetyState:
        risk_state = str(
            sparse_consensus_risk_state
            or self.UNKNOWN_RISK
        ).strip().upper()

        trust = (
            float(trust_score)
            if trust_score is not None
            else None
        )

        if trust is not None and (
            trust < 0.0
            or trust > 100.0
        ):
            raise ValueError(
                "trust_score must be between 0 and 100."
            )

        if (
            trust is None
            or risk_state == self.UNKNOWN_RISK
        ):
            return DecisionSafetyState(
                state=self.UNKNOWN,
                caution=True,
                high_caution=False,
                trust_score=trust,
                sparse_consensus_risk_state=(
                    risk_state
                ),
                explanation=(
                    "Decision safety cannot be fully "
                    "classified because model trust or "
                    "current regime risk is unavailable."
                ),
            )

        if risk_state == self.HIGH_RISK:
            return DecisionSafetyState(
                state=self.HIGH_CAUTION,
                caution=True,
                high_caution=True,
                trust_score=trust,
                sparse_consensus_risk_state=(
                    risk_state
                ),
                explanation=(
                    "Historical model trust is "
                    + (
                        "strong"
                        if trust >= 70.0
                        else "available"
                    )
                    + ", but the current sparse-consensus "
                    "regime is in its high-risk band."
                ),
            )

        if (
            risk_state == self.ELEVATED_RISK
            or trust < 55.0
        ):
            return DecisionSafetyState(
                state=self.CAUTION,
                caution=True,
                high_caution=False,
                trust_score=trust,
                sparse_consensus_risk_state=(
                    risk_state
                ),
                explanation=(
                    "Decision safety is classified as "
                    "caution because model trust or the "
                    "current sparse-consensus regime "
                    "requires additional care."
                ),
            )

        return DecisionSafetyState(
            state=self.NORMAL,
            caution=False,
            high_caution=False,
            trust_score=trust,
            sparse_consensus_risk_state=(
                risk_state
            ),
            explanation=(
                "Historical model trust is acceptable "
                "and the current sparse-consensus regime "
                "is classified as normal."
            ),
        )
