from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.transparent_v3_single_weight_optimiser import (
    SingleWeightOptimisationReport,
    TransparentV3SingleWeightOptimiser,
)


@dataclass(frozen=True)
class WeightConsensusSplit:
    training_offset: int
    validation_offset: int
    recommended_weight: float
    accepted: bool
    validation_brier_change: Optional[float]
    validation_log_loss_change: Optional[float]
    validation_accuracy_change: Optional[float]


@dataclass(frozen=True)
class WeightConsensusReport:
    model_version: str
    feature_name: str
    current_weight: float

    splits_requested: int
    splits_completed: int
    accepted_splits: int

    consensus_weight: Optional[float]
    consensus_votes: int
    consensus_percentage: float

    promotion_recommended: bool
    confidence: str
    reason: str

    splits: Tuple[WeightConsensusSplit, ...]


class TransparentV3WeightConsensusOptimiser:
    """
    Require repeated hold-out support before recommending a weight change.

    A candidate must:
    - be accepted on multiple independent validation samples;
    - receive the most accepted votes;
    - meet the configured minimum consensus proportion.
    """

    def __init__(
        self,
        *,
        single_weight_optimiser: Optional[
            TransparentV3SingleWeightOptimiser
        ] = None,
    ) -> None:
        self.single_weight_optimiser = (
            single_weight_optimiser
            or TransparentV3SingleWeightOptimiser()
        )

    def optimise(
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
        competition_code: Optional[str] = None,
    ) -> WeightConsensusReport:
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
                "must contain the same number of values."
            )

        if not 0 < minimum_consensus <= 1:
            raise ValueError(
                "minimum_consensus must be above zero "
                "and no greater than one."
            )

        reports = tuple(
            self.single_weight_optimiser.optimise(
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
            in zip(training, validation)
        )

        if not reports:
            raise ValueError(
                "No optimisation splits completed."
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
                votes.get(weight, 0) + 1
            )

        consensus_weight = None
        consensus_votes = 0

        if votes:
            consensus_weight, consensus_votes = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    -abs(item[0] - current_weight),
                ),
            )

        split_count = len(reports)

        consensus_percentage = (
            consensus_votes
            / split_count
            if split_count
            else 0.0
        )

        promotion_recommended = (
            consensus_weight is not None
            and consensus_weight != current_weight
            and consensus_percentage
            >= minimum_consensus
        )

        confidence = self._confidence(
            consensus_percentage
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
                "No candidate weight improved a "
                "hold-out validation split."
            )
        elif consensus_weight == current_weight:
            reason = (
                "The current weight retained the "
                "strongest consensus."
            )
        else:
            reason = (
                f"The leading candidate received "
                f"{consensus_votes}/{split_count} votes, "
                "below the required consensus."
            )

        return WeightConsensusReport(
            model_version=reports[0].model_version,
            feature_name=feature_name,
            current_weight=current_weight,
            splits_requested=len(training),
            splits_completed=split_count,
            accepted_splits=len(accepted_reports),
            consensus_weight=consensus_weight,
            consensus_votes=consensus_votes,
            consensus_percentage=round(
                consensus_percentage * 100.0,
                3,
            ),
            promotion_recommended=(
                promotion_recommended
            ),
            confidence=confidence,
            reason=reason,
            splits=tuple(
                self._summarise_split(report)
                for report in reports
            ),
        )

    @staticmethod
    def _summarise_split(
        report: SingleWeightOptimisationReport,
    ) -> WeightConsensusSplit:
        baseline = report.validation_baseline
        candidate = report.validation_candidate

        return WeightConsensusSplit(
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
            validation_brier_change=(
                TransparentV3WeightConsensusOptimiser
                ._difference(
                    baseline.brier_score,
                    candidate.brier_score,
                )
            ),
            validation_log_loss_change=(
                TransparentV3WeightConsensusOptimiser
                ._difference(
                    baseline.log_loss,
                    candidate.log_loss,
                )
            ),
            validation_accuracy_change=(
                TransparentV3WeightConsensusOptimiser
                ._difference(
                    candidate.accuracy,
                    baseline.accuracy,
                )
            ),
        )

    @staticmethod
    def _difference(
        left: Optional[float],
        right: Optional[float],
    ) -> Optional[float]:
        if left is None or right is None:
            return None

        return round(
            float(left) - float(right),
            6,
        )

    @staticmethod
    def _confidence(
        consensus_fraction: float,
    ) -> str:
        if consensus_fraction >= 1.0:
            return "high"

        if consensus_fraction >= 0.67:
            return "moderate"

        if consensus_fraction > 0:
            return "low"

        return "none"
