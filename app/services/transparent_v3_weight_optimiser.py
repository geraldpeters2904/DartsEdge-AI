from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

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
class WeightOptimisationScore:
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
class WeightOptimisationStep:
    iteration: int
    feature_name: str
    previous_weight: float
    candidate_weight: float
    accepted: bool
    score: WeightOptimisationScore


@dataclass(frozen=True)
class WeightOptimisationResult:
    model_version: str
    matches_evaluated: int
    baseline_score: WeightOptimisationScore
    best_score: WeightOptimisationScore
    initial_weights: Dict[str, float]
    best_weights: Dict[str, float]
    steps: Tuple[WeightOptimisationStep, ...]


class TransparentV3WeightOptimiser:
    """
    Deterministic coordinate-descent optimiser for Transparent v3.

    Candidate models are evaluated on the same historical match IDs. Ranking
    prefers lower Brier score, then lower log loss, then higher accuracy.
    """

    def optimise(
        self,
        db: Session,
        *,
        offset: int = 1000,
        limit: int = 500,
        step_sizes: Iterable[float] = (
            0.04,
            0.02,
            0.01,
        ),
        passes: int = 2,
        competition_code: Optional[str] = None,
    ) -> WeightOptimisationResult:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )
        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )
        if passes <= 0:
            raise ValueError(
                "passes must be greater than zero."
            )

        steps_to_try = tuple(
            float(value)
            for value in step_sizes
        )

        if (
            not steps_to_try
            or any(value <= 0 for value in steps_to_try)
        ):
            raise ValueError(
                "step_sizes must contain positive values."
            )

        match_ids = self._select_match_ids(
            db,
            offset=offset,
            limit=limit,
        )

        if not match_ids:
            raise ValueError(
                "No completed matches were selected."
            )

        engine = TransparentPredictionEngineV3()
        initial_weights = {
            feature.name: float(feature.weight)
            for feature in engine.features
        }

        baseline_score = self._evaluate(
            db,
            engine=engine,
            match_ids=match_ids,
            competition_code=competition_code,
        )

        best_engine = engine
        best_score = baseline_score
        steps = []
        iteration = 0

        for _pass in range(passes):
            improved_in_pass = False

            for step_size in steps_to_try:
                for feature_name in (
                    best_engine.feature_names()
                ):
                    current = self._weight(
                        best_engine,
                        feature_name,
                    )

                    candidates = (
                        max(0.0, current - step_size),
                        current + step_size,
                    )

                    local_engine = best_engine
                    local_score = best_score

                    for candidate in candidates:
                        iteration += 1
                        candidate_engine = (
                            best_engine
                            .with_feature_weight(
                                feature_name,
                                candidate,
                            )
                        )
                        candidate_score = self._evaluate(
                            db,
                            engine=candidate_engine,
                            match_ids=match_ids,
                            competition_code=(
                                competition_code
                            ),
                        )

                        accepted = (
                            candidate_score.ranking_key()
                            < local_score.ranking_key()
                        )

                        steps.append(
                            WeightOptimisationStep(
                                iteration=iteration,
                                feature_name=(
                                    feature_name
                                ),
                                previous_weight=current,
                                candidate_weight=(
                                    candidate
                                ),
                                accepted=accepted,
                                score=candidate_score,
                            )
                        )

                        if accepted:
                            local_engine = (
                                candidate_engine
                            )
                            local_score = (
                                candidate_score
                            )

                    if (
                        local_score.ranking_key()
                        < best_score.ranking_key()
                    ):
                        best_engine = local_engine
                        best_score = local_score
                        improved_in_pass = True

            if not improved_in_pass:
                break

        return WeightOptimisationResult(
            model_version=(
                best_engine.MODEL_VERSION
            ),
            matches_evaluated=len(match_ids),
            baseline_score=baseline_score,
            best_score=best_score,
            initial_weights=initial_weights,
            best_weights={
                feature.name: float(
                    feature.weight
                )
                for feature in (
                    best_engine.features
                )
            },
            steps=tuple(steps),
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

    @staticmethod
    def _weight(
        engine: TransparentPredictionEngineV3,
        feature_name: str,
    ) -> float:
        return next(
            float(feature.weight)
            for feature in engine.features
            if feature.name == feature_name
        )

    @staticmethod
    def _evaluate(
        db: Session,
        *,
        engine: TransparentPredictionEngineV3,
        match_ids,
        competition_code: Optional[str],
    ) -> WeightOptimisationScore:
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

        return WeightOptimisationScore(
            accuracy=report.accuracy,
            brier_score=(
                report.average_brier_score
            ),
            log_loss=(
                report.average_log_loss
            ),
        )
