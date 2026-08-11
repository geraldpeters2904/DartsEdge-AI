from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33_dual_low_history import (
    TransparentPredictionEngineV33DualLowHistory,
)


@dataclass(frozen=True)
class V33DualLowHistoryCandidateEvidence:
    multiplier: float
    accuracy: Optional[float]
    brier_score: Optional[float]
    log_loss: Optional[float]

    def ranking_key(self):
        return (
            self.brier_score
            if self.brier_score is not None
            else float("inf"),
            self.log_loss
            if self.log_loss is not None
            else float("inf"),
            -(
                self.accuracy
                if self.accuracy is not None
                else -1.0
            ),
        )


@dataclass(frozen=True)
class V33DualLowHistoryEvidenceReport:
    model_version: str
    history_threshold: int

    training_offset: int
    training_limit: int
    training_matches_evaluated: int

    validation_offset: int
    validation_limit: int
    validation_matches_evaluated: int

    training_candidates: Tuple[
        V33DualLowHistoryCandidateEvidence,
        ...
    ]

    training_winner: V33DualLowHistoryCandidateEvidence

    validation_baseline: V33DualLowHistoryCandidateEvidence
    validation_candidate: V33DualLowHistoryCandidateEvidence

    recommended_multiplier: float
    recommendation_accepted: bool
    recommendation_reason: str


class CurrentMatchEnrichmentV33DualLowHistoryEvidenceService:
    """
    Read-only training/hold-out evidence for scaling recent_win_rate
    only when BOTH players have very low pre-match history.

    Candidate multipliers are selected on a deterministic training
    window and tested against unchanged v3.3 on an independent
    hold-out window.

    This service never modifies or registers the production model.
    """

    def analyse(
        self,
        db: Session,
        *,
        candidate_multipliers: Iterable[float],
        training_offset: int,
        training_limit: int,
        validation_offset: int,
        validation_limit: int,
        history_threshold: int = 3,
        competition_code: Optional[str] = "MODUS",
    ) -> V33DualLowHistoryEvidenceReport:
        if training_offset < 0:
            raise ValueError(
                "training_offset cannot be negative."
            )

        if validation_offset < 0:
            raise ValueError(
                "validation_offset cannot be negative."
            )

        if training_limit <= 0:
            raise ValueError(
                "training_limit must be greater than zero."
            )

        if validation_limit <= 0:
            raise ValueError(
                "validation_limit must be greater than zero."
            )

        if history_threshold <= 0:
            raise ValueError(
                "history_threshold must be greater than zero."
            )

        if self._windows_overlap(
            training_offset,
            training_limit,
            validation_offset,
            validation_limit,
        ):
            raise ValueError(
                "Training and validation windows overlap."
            )

        candidates = tuple(
            sorted({
                round(
                    float(value),
                    6,
                )
                for value in candidate_multipliers
            })
        )

        if not candidates:
            raise ValueError(
                "Enter at least one candidate multiplier."
            )

        if any(
            value < 0.0
            or value > 1.0
            for value in candidates
        ):
            raise ValueError(
                "Candidate multipliers must be "
                "between 0 and 1."
            )

        if 1.0 not in candidates:
            raise ValueError(
                "Candidate multipliers must include "
                "1.0 as the unchanged v3.3 baseline."
            )

        training_results = tuple(
            self._evaluate(
                db,
                multiplier=multiplier,
                history_threshold=history_threshold,
                offset=training_offset,
                limit=training_limit,
                competition_code=competition_code,
            )
            for multiplier in candidates
        )

        training_winner = min(
            training_results,
            key=lambda item: item.ranking_key(),
        )

        validation_baseline = self._evaluate(
            db,
            multiplier=1.0,
            history_threshold=history_threshold,
            offset=validation_offset,
            limit=validation_limit,
            competition_code=competition_code,
        )

        validation_candidate = self._evaluate(
            db,
            multiplier=training_winner.multiplier,
            history_threshold=history_threshold,
            offset=validation_offset,
            limit=validation_limit,
            competition_code=competition_code,
        )

        accepted, reason = self._recommendation(
            recommended_multiplier=(
                training_winner.multiplier
            ),
            baseline=validation_baseline,
            candidate=validation_candidate,
        )

        return V33DualLowHistoryEvidenceReport(
            model_version=(
                "transparent-v3.3-dual-low-history"
            ),
            history_threshold=history_threshold,
            training_offset=training_offset,
            training_limit=training_limit,
            training_matches_evaluated=(
                self._matches_evaluated(
                    db,
                    multiplier=1.0,
                    history_threshold=history_threshold,
                    offset=training_offset,
                    limit=training_limit,
                    competition_code=competition_code,
                )
            ),
            validation_offset=validation_offset,
            validation_limit=validation_limit,
            validation_matches_evaluated=(
                self._matches_evaluated(
                    db,
                    multiplier=1.0,
                    history_threshold=history_threshold,
                    offset=validation_offset,
                    limit=validation_limit,
                    competition_code=competition_code,
                )
            ),
            training_candidates=training_results,
            training_winner=training_winner,
            validation_baseline=validation_baseline,
            validation_candidate=validation_candidate,
            recommended_multiplier=(
                training_winner.multiplier
            ),
            recommendation_accepted=accepted,
            recommendation_reason=reason,
        )

    @staticmethod
    def _evaluate(
        db,
        *,
        multiplier,
        history_threshold,
        offset,
        limit,
        competition_code,
    ):
        engine = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=multiplier,
                history_threshold=history_threshold,
            )
        )

        report = (
            CurrentMatchEnrichmentV33ValidationService(
                prediction_engine=engine,
            )
            .validate(
                db,
                offset=offset,
                limit=limit,
                competition_code=competition_code,
            )
        )

        return V33DualLowHistoryCandidateEvidence(
            multiplier=float(multiplier),
            accuracy=report.accuracy,
            brier_score=report.average_brier_score,
            log_loss=report.average_log_loss,
        )

    @staticmethod
    def _matches_evaluated(
        db,
        *,
        multiplier,
        history_threshold,
        offset,
        limit,
        competition_code,
    ):
        engine = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=multiplier,
                history_threshold=history_threshold,
            )
        )

        return (
            CurrentMatchEnrichmentV33ValidationService(
                prediction_engine=engine,
            )
            .validate(
                db,
                offset=offset,
                limit=limit,
                competition_code=competition_code,
            )
            .matches_evaluated
        )

    @staticmethod
    def _windows_overlap(
        first_offset,
        first_limit,
        second_offset,
        second_limit,
    ):
        first_end = (
            first_offset + first_limit
        )

        second_end = (
            second_offset + second_limit
        )

        return (
            first_offset < second_end
            and second_offset < first_end
        )

    @staticmethod
    def _recommendation(
        *,
        recommended_multiplier,
        baseline,
        candidate,
    ):
        if recommended_multiplier == 1.0:
            return (
                False,
                "Unchanged v3.3 remained best "
                "on the training window.",
            )

        if (
            baseline.brier_score is None
            or baseline.log_loss is None
            or candidate.brier_score is None
            or candidate.log_loss is None
        ):
            return (
                False,
                "Insufficient hold-out evidence.",
            )

        brier_improved = (
            candidate.brier_score
            < baseline.brier_score
        )

        log_loss_improved = (
            candidate.log_loss
            < baseline.log_loss
        )

        accuracy_safe = (
            baseline.accuracy is None
            or candidate.accuracy is None
            or candidate.accuracy
            >= baseline.accuracy - 2.0
        )

        if (
            brier_improved
            and log_loss_improved
            and accuracy_safe
        ):
            return (
                True,
                "The dual-low-history challenger improved "
                "both hold-out probability metrics without "
                "materially reducing accuracy.",
            )

        return (
            False,
            "The dual-low-history challenger did not satisfy "
            "the hold-out acceptance criteria.",
        )
