from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_weight_evidence_service import (
    CurrentMatchEnrichmentV33WeightEvidenceService,
)


@dataclass(frozen=True)
class V33WeightConsensusSplit:
    training_offset: int
    validation_offset: int
    recommended_weight: float
    accepted: bool

    validation_accuracy_change: Optional[float]
    validation_brier_change: Optional[float]
    validation_log_loss_change: Optional[float]


@dataclass(frozen=True)
class V33WeightConsensusReport:
    model_version: str
    feature_name: str
    current_weight: float

    splits_completed: int
    accepted_splits: int

    consensus_weight: Optional[float]
    consensus_votes: int
    consensus_percentage: float

    promotion_recommended: bool
    reason: str

    splits: Tuple[
        V33WeightConsensusSplit,
        ...
    ]


class CurrentMatchEnrichmentV33WeightConsensusService:
    """
    Require repeated independent hold-out support before recommending
    any transparent-v3.3 feature-weight change.

    This service is read-only and never modifies the active model.
    """

    def __init__(
        self,
        *,
        weight_evidence_service=None,
    ) -> None:
        self.weight_evidence_service = (
            weight_evidence_service
            or CurrentMatchEnrichmentV33WeightEvidenceService()
        )

    def analyse(
        self,
        db: Session,
        *,
        feature_name: str,
        candidate_weights: Iterable[float],
        training_offsets: Iterable[int],
        validation_offsets: Iterable[int],
        training_limit: int = 500,
        validation_limit: int = 500,
        minimum_consensus: float = 0.67,
        competition_code: Optional[str] = "MODUS",
    ) -> V33WeightConsensusReport:
        training = tuple(
            int(value)
            for value in training_offsets
        )

        validation = tuple(
            int(value)
            for value in validation_offsets
        )

        if not training:
            raise ValueError(
                "Enter at least one training offset."
            )

        if len(training) != len(validation):
            raise ValueError(
                "Training and validation offsets "
                "must have equal lengths."
            )

        if not 0 < minimum_consensus <= 1:
            raise ValueError(
                "minimum_consensus must be above "
                "zero and no greater than one."
            )

        reports = tuple(
            self.weight_evidence_service.analyse(
                db,
                feature_name=feature_name,
                candidate_weights=candidate_weights,
                training_offset=training_offset,
                training_limit=training_limit,
                validation_offset=validation_offset,
                validation_limit=validation_limit,
                competition_code=competition_code,
            )
            for training_offset, validation_offset
            in zip(
                training,
                validation,
            )
        )

        if not reports:
            raise ValueError(
                "No weight evidence splits completed."
            )

        current_weight = reports[0].current_weight

        accepted_reports = tuple(
            report
            for report in reports
            if report.recommendation_accepted
        )

        votes = {}

        for report in accepted_reports:
            weight = round(
                float(report.recommended_weight),
                6,
            )

            votes[weight] = (
                votes.get(weight, 0)
                + 1
            )

        consensus_weight = None
        consensus_votes = 0

        if votes:
            consensus_weight, consensus_votes = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    -abs(
                        item[0]
                        - current_weight
                    ),
                ),
            )

        split_count = len(reports)

        consensus_fraction = (
            consensus_votes
            / split_count
            if split_count
            else 0.0
        )

        promotion_recommended = (
            consensus_weight is not None
            and consensus_weight
            != current_weight
            and consensus_fraction
            >= minimum_consensus
        )

        if promotion_recommended:
            reason = (
                f"Weight {consensus_weight:.6f} "
                f"was accepted on "
                f"{consensus_votes}/{split_count} "
                "independent hold-out splits."
            )
        elif consensus_weight is None:
            reason = (
                "No alternative weight received "
                "accepted hold-out support."
            )
        elif consensus_weight == current_weight:
            reason = (
                "The current v3.3 weight retained "
                "the strongest consensus."
            )
        else:
            reason = (
                f"The leading alternative received "
                f"{consensus_votes}/{split_count} votes, "
                "below the required consensus."
            )

        return V33WeightConsensusReport(
            model_version=reports[0].model_version,
            feature_name=feature_name,
            current_weight=current_weight,
            splits_completed=split_count,
            accepted_splits=len(
                accepted_reports
            ),
            consensus_weight=consensus_weight,
            consensus_votes=consensus_votes,
            consensus_percentage=round(
                consensus_fraction * 100.0,
                3,
            ),
            promotion_recommended=(
                promotion_recommended
            ),
            reason=reason,
            splits=tuple(
                self._summarise_split(report)
                for report in reports
            ),
        )

    @staticmethod
    def _summarise_split(
        report,
    ) -> V33WeightConsensusSplit:
        baseline = (
            report.validation_baseline
        )
        candidate = (
            report.validation_candidate
        )

        return V33WeightConsensusSplit(
            training_offset=(
                report.training_offset
            ),
            validation_offset=(
                report.validation_offset
            ),
            recommended_weight=(
                report.recommended_weight
            ),
            accepted=(
                report.recommendation_accepted
            ),
            validation_accuracy_change=(
                CurrentMatchEnrichmentV33WeightConsensusService
                ._difference(
                    candidate.accuracy,
                    baseline.accuracy,
                )
            ),
            validation_brier_change=(
                CurrentMatchEnrichmentV33WeightConsensusService
                ._difference(
                    baseline.brier_score,
                    candidate.brier_score,
                )
            ),
            validation_log_loss_change=(
                CurrentMatchEnrichmentV33WeightConsensusService
                ._difference(
                    baseline.log_loss,
                    candidate.log_loss,
                )
            ),
        )

    @staticmethod
    def _difference(
        left,
        right,
    ):
        if left is None or right is None:
            return None

        return round(
            float(left) - float(right),
            6,
        )
