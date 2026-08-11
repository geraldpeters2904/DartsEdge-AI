from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_calibration_evidence_service import (
    CurrentMatchEnrichmentV33CalibrationEvidenceService,
)


@dataclass(frozen=True)
class V33CalibrationConsensusSplit:
    training_offset: int
    validation_offset: int

    recommended_shrink_fraction: float
    accepted: bool

    accuracy_change: Optional[float]
    brier_gain: Optional[float]
    log_loss_gain: Optional[float]


@dataclass(frozen=True)
class V33CalibrationConsensusReport:
    model_version: str

    probability_lower: float
    probability_upper: float
    minimum_history_upper: int

    splits_completed: int
    accepted_splits: int
    accepted_percentage: float

    calibration_supported: bool

    consensus_shrink_fraction: Optional[float]
    consensus_votes: int
    consensus_percentage: float

    exact_shrink_promotion_recommended: bool

    calibration_reason: str
    shrink_reason: str

    splits: Tuple[
        V33CalibrationConsensusSplit,
        ...
    ]


class CurrentMatchEnrichmentV33CalibrationConsensusService:
    """
    Require repeated independent hold-out support before promoting
    low-history calibration for transparent-v3.3.

    Two decisions are kept separate:

    1. Whether low-history calibration itself has repeated support.
    2. Whether one exact shrink fraction has enough consensus.

    This service is read-only and never modifies the active model.
    """

    def __init__(
        self,
        *,
        evidence_service=None,
    ) -> None:
        self.evidence_service = (
            evidence_service
            or CurrentMatchEnrichmentV33CalibrationEvidenceService()
        )

    def analyse(
        self,
        db: Session,
        *,
        candidate_shrink_fractions: Iterable[float],
        training_offsets: Iterable[int],
        validation_offsets: Iterable[int],
        training_limit: int = 500,
        validation_limit: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        minimum_history_upper: int = 10,
        minimum_calibration_support: float = 0.67,
        minimum_exact_consensus: float = 0.67,
        minimum_splits: int = 3,
        competition_code: Optional[str] = "MODUS",
    ) -> V33CalibrationConsensusReport:
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

        if minimum_splits <= 0:
            raise ValueError(
                "minimum_splits must be greater than zero."
            )

        if not 0 < minimum_calibration_support <= 1:
            raise ValueError(
                "minimum_calibration_support must be above "
                "zero and no greater than one."
            )

        if not 0 < minimum_exact_consensus <= 1:
            raise ValueError(
                "minimum_exact_consensus must be above "
                "zero and no greater than one."
            )

        reports = tuple(
            self.evidence_service.analyse(
                db,
                candidate_shrink_fractions=(
                    candidate_shrink_fractions
                ),
                training_offset=training_offset,
                training_limit=training_limit,
                validation_offset=validation_offset,
                validation_limit=validation_limit,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                minimum_history_upper=minimum_history_upper,
                competition_code=competition_code,
            )
            for training_offset, validation_offset
            in zip(
                training,
                validation,
            )
        )

        split_count = len(reports)

        accepted_reports = tuple(
            report
            for report in reports
            if report.recommendation_accepted
        )

        accepted_count = len(
            accepted_reports
        )

        accepted_fraction = (
            accepted_count
            / split_count
            if split_count
            else 0.0
        )

        calibration_supported = (
            split_count >= minimum_splits
            and accepted_fraction
            >= minimum_calibration_support
        )

        votes = {}

        for report in accepted_reports:
            shrink = round(
                float(
                    report
                    .recommended_shrink_fraction
                ),
                6,
            )

            votes[shrink] = (
                votes.get(shrink, 0)
                + 1
            )

        consensus_shrink = None
        consensus_votes = 0

        if votes:
            consensus_shrink, consensus_votes = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    item[0],
                ),
            )

        consensus_fraction = (
            consensus_votes
            / split_count
            if split_count
            else 0.0
        )

        exact_promotion = (
            calibration_supported
            and consensus_shrink is not None
            and consensus_shrink > 0.0
            and consensus_fraction
            >= minimum_exact_consensus
        )

        if calibration_supported:
            calibration_reason = (
                "Low-history calibration received "
                f"accepted hold-out support on "
                f"{accepted_count}/{split_count} splits."
            )
        elif split_count < minimum_splits:
            calibration_reason = (
                "Insufficient independent splits completed "
                "for calibration promotion."
            )
        else:
            calibration_reason = (
                "Low-history calibration did not reach "
                "the required accepted hold-out support."
            )

        if exact_promotion:
            shrink_reason = (
                f"Shrink {consensus_shrink:.6f} received "
                f"{consensus_votes}/{split_count} votes "
                "and reached the required exact consensus."
            )
        elif consensus_shrink is None:
            shrink_reason = (
                "No non-zero shrink fraction received "
                "accepted hold-out support."
            )
        else:
            shrink_reason = (
                f"The leading shrink {consensus_shrink:.6f} "
                f"received {consensus_votes}/{split_count} votes, "
                "below the required exact consensus."
            )

        return V33CalibrationConsensusReport(
            model_version=reports[0].model_version,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            minimum_history_upper=minimum_history_upper,
            splits_completed=split_count,
            accepted_splits=accepted_count,
            accepted_percentage=round(
                accepted_fraction * 100.0,
                3,
            ),
            calibration_supported=(
                calibration_supported
            ),
            consensus_shrink_fraction=(
                consensus_shrink
            ),
            consensus_votes=consensus_votes,
            consensus_percentage=round(
                consensus_fraction * 100.0,
                3,
            ),
            exact_shrink_promotion_recommended=(
                exact_promotion
            ),
            calibration_reason=(
                calibration_reason
            ),
            shrink_reason=(
                shrink_reason
            ),
            splits=tuple(
                self._summarise_split(report)
                for report in reports
            ),
        )

    @staticmethod
    def _summarise_split(
        report,
    ) -> V33CalibrationConsensusSplit:
        baseline = (
            report.validation_baseline
        )

        candidate = (
            report.validation_candidate
        )

        return V33CalibrationConsensusSplit(
            training_offset=(
                report.training_offset
            ),
            validation_offset=(
                report.validation_offset
            ),
            recommended_shrink_fraction=(
                report.recommended_shrink_fraction
            ),
            accepted=(
                report.recommendation_accepted
            ),
            accuracy_change=(
                CurrentMatchEnrichmentV33CalibrationConsensusService
                ._difference(
                    candidate.accuracy,
                    baseline.accuracy,
                )
            ),
            brier_gain=(
                CurrentMatchEnrichmentV33CalibrationConsensusService
                ._difference(
                    baseline.brier_score,
                    candidate.brier_score,
                )
            ),
            log_loss_gain=(
                CurrentMatchEnrichmentV33CalibrationConsensusService
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
