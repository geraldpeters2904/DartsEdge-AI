from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
)
from app.services.transparent_prediction_engine_v3 import (
    TransparentPredictionEngineV3,
)


@dataclass(frozen=True)
class WeightCandidateResult:
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
class SingleWeightOptimisationReport:
    model_version: str
    feature_name: str
    current_weight: float
    recommended_weight: float

    training_offset: int
    training_matches: int
    validation_offset: int
    validation_matches: int

    training_baseline: WeightCandidateResult
    training_candidates: Tuple[
        WeightCandidateResult,
        ...
    ]
    training_winner: WeightCandidateResult

    validation_baseline: WeightCandidateResult
    validation_candidate: WeightCandidateResult

    recommendation_accepted: bool
    recommendation_reason: str


class TransparentV3SingleWeightOptimiser:
    """
    Optimise one v3 feature weight using training and hold-out data.

    Candidate ranking prioritises lower Brier score, then lower log loss,
    followed by higher winner-prediction accuracy.
    """

    def optimise(
        self,
        db: Session,
        *,
        feature_name: str,
        candidate_weights: Iterable[float],
        training_offset: int = 1000,
        training_limit: int = 500,
        validation_offset: int = 2500,
        validation_limit: int = 500,
        competition_code: Optional[str] = None,
    ) -> SingleWeightOptimisationReport:
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

        if any(value < 0 for value in candidates):
            raise ValueError(
                "Candidate weights cannot be negative."
            )

        baseline_engine = (
            TransparentPredictionEngineV3()
        )

        if name not in baseline_engine.feature_names():
            raise ValueError(
                f"Unknown prediction feature: {name}."
            )

        current_weight = next(
            float(feature.weight)
            for feature in baseline_engine.features
            if feature.name == name
        )

        training_ids = self._select_match_ids(
            db,
            offset=training_offset,
            limit=training_limit,
        )

        validation_ids = self._select_match_ids(
            db,
            offset=validation_offset,
            limit=validation_limit,
        )

        if not training_ids:
            raise ValueError(
                "No training matches were selected."
            )

        if not validation_ids:
            raise ValueError(
                "No validation matches were selected."
            )

        overlap = (
            set(training_ids)
            & set(validation_ids)
        )

        if overlap:
            raise ValueError(
                "Training and validation match sets overlap."
            )

        training_baseline = self._evaluate(
            db,
            engine=baseline_engine,
            match_ids=training_ids,
            competition_code=competition_code,
            weight=current_weight,
        )

        training_results = tuple(
            self._evaluate(
                db,
                engine=(
                    baseline_engine
                    .with_feature_weight(
                        name,
                        weight,
                    )
                ),
                match_ids=training_ids,
                competition_code=competition_code,
                weight=weight,
            )
            for weight in candidates
        )

        training_winner = min(
            (
                training_baseline,
                *training_results,
            ),
            key=lambda item: item.ranking_key(),
        )

        recommended_weight = (
            training_winner.weight
        )

        validation_baseline = self._evaluate(
            db,
            engine=baseline_engine,
            match_ids=validation_ids,
            competition_code=competition_code,
            weight=current_weight,
        )

        validation_candidate = self._evaluate(
            db,
            engine=(
                baseline_engine
                .with_feature_weight(
                    name,
                    recommended_weight,
                )
            ),
            match_ids=validation_ids,
            competition_code=competition_code,
            weight=recommended_weight,
        )

        accepted, reason = (
            self._recommendation(
                current_weight=current_weight,
                recommended_weight=(
                    recommended_weight
                ),
                baseline=validation_baseline,
                candidate=validation_candidate,
            )
        )

        return SingleWeightOptimisationReport(
            model_version=(
                baseline_engine.MODEL_VERSION
            ),
            feature_name=name,
            current_weight=current_weight,
            recommended_weight=(
                recommended_weight
            ),
            training_offset=training_offset,
            training_matches=len(training_ids),
            validation_offset=validation_offset,
            validation_matches=(
                len(validation_ids)
            ),
            training_baseline=(
                training_baseline
            ),
            training_candidates=(
                training_results
            ),
            training_winner=training_winner,
            validation_baseline=(
                validation_baseline
            ),
            validation_candidate=(
                validation_candidate
            ),
            recommendation_accepted=accepted,
            recommendation_reason=reason,
        )

    @staticmethod
    def _recommendation(
        *,
        current_weight: float,
        recommended_weight: float,
        baseline: WeightCandidateResult,
        candidate: WeightCandidateResult,
    ) -> tuple[bool, str]:
        if recommended_weight == current_weight:
            return (
                False,
                "The current weight remained best "
                "on the training sample.",
            )

        if (
            candidate.ranking_key()
            < baseline.ranking_key()
        ):
            return (
                True,
                "The candidate improved hold-out "
                "probability quality.",
            )

        return (
            False,
            "The training winner did not improve "
            "the hold-out validation sample.",
        )

    @staticmethod
    def _evaluate(
        db: Session,
        *,
        engine: TransparentPredictionEngineV3,
        match_ids,
        competition_code: Optional[str],
        weight: float,
    ) -> WeightCandidateResult:
        report = PredictionValidationEngine(
            snapshot_engine=(
                AdvancedHistoricalSnapshotEngine()
            ),
            prediction_engine=engine,
        ).validate_matches(
            db,
            match_ids=match_ids,
            competition_code=competition_code,
            include_records=False,
        )

        return WeightCandidateResult(
            weight=weight,
            accuracy=report.accuracy,
            brier_score=(
                report.average_brier_score
            ),
            log_loss=(
                report.average_log_loss
            ),
        )

    @staticmethod
    def _select_match_ids(
        db: Session,
        *,
        offset: int,
        limit: int,
    ) -> list[int]:
        rows = (
            db.query(Match.id)
            .filter(
                Match.status == "completed"
            )
            .order_by(
                Match.date.asc(),
                Match.id.asc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            int(match_id)
            for (match_id,) in rows
        ]
