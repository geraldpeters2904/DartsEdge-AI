from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33WeightCandidateEvidence:
    weight: float
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
class V33WeightEvidenceReport:
    model_version: str
    feature_name: str
    current_weight: float

    training_offset: int
    training_limit: int
    training_matches_evaluated: int

    validation_offset: int
    validation_limit: int
    validation_matches_evaluated: int

    training_candidates: Tuple[
        V33WeightCandidateEvidence, ...
    ]
    training_winner: V33WeightCandidateEvidence

    validation_baseline: V33WeightCandidateEvidence
    validation_candidate: V33WeightCandidateEvidence

    recommended_weight: float
    recommendation_accepted: bool
    recommendation_reason: str


class CurrentMatchEnrichmentV33WeightEvidenceService:
    """
    Read-only single-feature weight evidence for transparent-v3.3.

    Candidate weights are compared on a deterministic training
    window. The training winner is then tested against the current
    v3.3 weight on an independent hold-out validation window.

    This service never modifies the active model.
    """

    def analyse(
        self,
        db: Session,
        *,
        feature_name: str,
        candidate_weights: Iterable[float],
        training_offset: int,
        training_limit: int,
        validation_offset: int,
        validation_limit: int,
        competition_code: Optional[str] = "MODUS",
    ) -> V33WeightEvidenceReport:
        name = str(feature_name or "").strip()

        if not name:
            raise ValueError(
                "Enter a feature name."
            )

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
                round(float(value), 6)
                for value in candidate_weights
            })
        )

        if not candidates:
            raise ValueError(
                "Enter at least one candidate weight."
            )

        if any(
            value < 0
            for value in candidates
        ):
            raise ValueError(
                "Candidate weights cannot be negative."
            )

        baseline_engine = (
            TransparentPredictionEngineV33()
        )

        feature = next(
            (
                item
                for item in baseline_engine.features
                if item.name == name
            ),
            None,
        )

        if feature is None:
            raise ValueError(
                f"Unknown prediction feature: {name}."
            )

        current_weight = float(feature.weight)

        training_results = tuple(
            self._evaluate(
                db,
                engine=self._engine_with_weight(
                    baseline_engine,
                    name,
                    weight,
                ),
                weight=weight,
                offset=training_offset,
                limit=training_limit,
                competition_code=competition_code,
            )
            for weight in candidates
        )

        training_winner = min(
            training_results,
            key=lambda item: item.ranking_key(),
        )

        validation_baseline = self._evaluate(
            db,
            engine=baseline_engine,
            weight=current_weight,
            offset=validation_offset,
            limit=validation_limit,
            competition_code=competition_code,
        )

        validation_candidate = self._evaluate(
            db,
            engine=self._engine_with_weight(
                baseline_engine,
                name,
                training_winner.weight,
            ),
            weight=training_winner.weight,
            offset=validation_offset,
            limit=validation_limit,
            competition_code=competition_code,
        )

        accepted, reason = self._recommendation(
            current_weight=current_weight,
            recommended_weight=training_winner.weight,
            baseline=validation_baseline,
            candidate=validation_candidate,
        )

        training_matches_evaluated = (
            self._matches_evaluated(
                db,
                engine=baseline_engine,
                offset=training_offset,
                limit=training_limit,
                competition_code=competition_code,
            )
        )

        validation_matches_evaluated = (
            self._matches_evaluated(
                db,
                engine=baseline_engine,
                offset=validation_offset,
                limit=validation_limit,
                competition_code=competition_code,
            )
        )

        return V33WeightEvidenceReport(
            model_version=baseline_engine.MODEL_VERSION,
            feature_name=name,
            current_weight=current_weight,
            training_offset=training_offset,
            training_limit=training_limit,
            training_matches_evaluated=(
                training_matches_evaluated
            ),
            validation_offset=validation_offset,
            validation_limit=validation_limit,
            validation_matches_evaluated=(
                validation_matches_evaluated
            ),
            training_candidates=training_results,
            training_winner=training_winner,
            validation_baseline=validation_baseline,
            validation_candidate=validation_candidate,
            recommended_weight=training_winner.weight,
            recommendation_accepted=accepted,
            recommendation_reason=reason,
        )

    @staticmethod
    def _engine_with_weight(
        baseline_engine,
        feature_name,
        weight,
    ):
        features = tuple(
            type(feature)(
                name=feature.name,
                weight=float(weight),
                scale=feature.scale,
                edge_getter=feature.edge_getter,
                label=feature.label,
            )
            if feature.name == feature_name
            else feature
            for feature in baseline_engine.features
        )

        return TransparentPredictionEngineV33(
            features=features,
            logistic_strength=(
                baseline_engine.logistic_strength
            ),
        )

    @staticmethod
    def _evaluate(
        db,
        *,
        engine,
        weight,
        offset,
        limit,
        competition_code,
    ):
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

        return V33WeightCandidateEvidence(
            weight=float(weight),
            accuracy=report.accuracy,
            brier_score=report.average_brier_score,
            log_loss=report.average_log_loss,
        )

    @staticmethod
    def _matches_evaluated(
        db,
        *,
        engine,
        offset,
        limit,
        competition_code,
    ):
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
        first_end = first_offset + first_limit
        second_end = second_offset + second_limit

        return (
            first_offset < second_end
            and second_offset < first_end
        )

    @staticmethod
    def _recommendation(
        *,
        current_weight,
        recommended_weight,
        baseline,
        candidate,
    ):
        if recommended_weight == current_weight:
            return (
                False,
                "The current v3.3 weight remained best "
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
                "The candidate improved both hold-out "
                "probability metrics without materially "
                "reducing accuracy.",
            )

        return (
            False,
            "The candidate did not satisfy the hold-out "
            "acceptance criteria.",
        )
