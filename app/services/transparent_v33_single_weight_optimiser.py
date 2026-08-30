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
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33WeightCandidateResult:
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
class V33SingleWeightOptimisationReport:
    model_version: str
    feature_name: str
    current_weight: float
    recommended_weight: float

    training_offset: int
    training_matches: int
    validation_offset: int
    validation_matches: int

    training_baseline: V33WeightCandidateResult
    training_candidates: Tuple[
        V33WeightCandidateResult,
        ...
    ]
    training_winner: V33WeightCandidateResult

    validation_baseline: V33WeightCandidateResult
    validation_candidate: V33WeightCandidateResult

    recommendation_accepted: bool
    recommendation_reason: str


class TransparentV33SingleWeightOptimiser:
    """
    Optimise one transparent-v3.3 feature weight using
    a training sample followed by an independent hold-out sample.

    Candidate ranking prioritises:
    1. lower Brier score
    2. lower log loss
    3. higher winner-prediction accuracy

    No model weights are changed automatically.
    """

    def optimise(
        self,
        db: Session,
        *,
        feature_name: str,
        candidate_weights: Iterable[float],
        training_offset: int = 0,
        training_limit: int = 1500,
        validation_offset: int = 1500,
        validation_limit: int = 1500,
        competition_code: Optional[str] = "MODUS",
    ) -> V33SingleWeightOptimisationReport:

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
            sorted(
                {
                    round(float(value), 6)
                    for value in candidate_weights
                }
            )
        )

        if not candidates:
            raise ValueError(
                "Enter at least one candidate weight."
            )

        if any(value < 0 for value in candidates):
            raise ValueError(
                "Candidate weights cannot be negative."
            )

        baseline_engine = TransparentPredictionEngineV33()

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

        training_snapshots = self._build_snapshots(
            db,
            match_ids=training_ids,
            competition_code=competition_code,
        )

        validation_snapshots = self._build_snapshots(
            db,
            match_ids=validation_ids,
            competition_code=competition_code,
        )

        training_baseline = self._evaluate_cached(
            engine=baseline_engine,
            snapshots=training_snapshots,
            weight=current_weight,
        )

        training_results = tuple(
            self._evaluate_cached(
                engine=(
                    baseline_engine.with_feature_weight(
                        name,
                        weight,
                    )
                ),
                snapshots=training_snapshots,
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

        validation_baseline = self._evaluate_cached(
            engine=baseline_engine,
            snapshots=validation_snapshots,
            weight=current_weight,
        )

        validation_candidate = self._evaluate_cached(
            engine=(
                baseline_engine.with_feature_weight(
                    name,
                    recommended_weight,
                )
            ),
            snapshots=validation_snapshots,
            weight=recommended_weight,
        )

        accepted, reason = self._recommendation(
            current_weight=current_weight,
            recommended_weight=recommended_weight,
            baseline=validation_baseline,
            candidate=validation_candidate,
        )

        return V33SingleWeightOptimisationReport(
            model_version=baseline_engine.MODEL_VERSION,
            feature_name=name,
            current_weight=current_weight,
            recommended_weight=recommended_weight,
            training_offset=training_offset,
            training_matches=len(training_ids),
            validation_offset=validation_offset,
            validation_matches=len(validation_ids),
            training_baseline=training_baseline,
            training_candidates=training_results,
            training_winner=training_winner,
            validation_baseline=validation_baseline,
            validation_candidate=validation_candidate,
            recommendation_accepted=accepted,
            recommendation_reason=reason,
        )

    @staticmethod
    def _recommendation(
        *,
        current_weight: float,
        recommended_weight: float,
        baseline: V33WeightCandidateResult,
        candidate: V33WeightCandidateResult,
    ) -> tuple[bool, str]:

        if recommended_weight == current_weight:
            return (
                False,
                "The current weight remained best "
                "on the training sample.",
            )

        if candidate.ranking_key() < baseline.ranking_key():
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
    def _build_snapshots(
        db: Session,
        *,
        match_ids,
        competition_code: Optional[str],
    ):
        snapshot_engine = AdvancedHistoricalSnapshotEngine()
        snapshots = []

        matches = {
            match.id: match
            for match in (
                db.query(Match)
                .filter(Match.id.in_(tuple(match_ids)))
                .all()
            )
        }

        for match_id in match_ids:
            match = matches.get(int(match_id))

            if (
                match is None
                or not PredictionValidationEngine._has_valid_result(
                    match
                )
            ):
                continue

            try:
                snapshot = snapshot_engine.build_match_snapshot(
                    db,
                    match.id,
                    competition_code=competition_code,
                )
            except Exception:
                continue

            snapshots.append((match, snapshot))

        return tuple(snapshots)

    @staticmethod
    def _evaluate_cached(
        *,
        engine: TransparentPredictionEngineV33,
        snapshots,
        weight: float,
    ) -> V33WeightCandidateResult:
        records = []

        for match, snapshot in snapshots:
            try:
                prediction = engine.predict(snapshot)
            except Exception:
                continue

            actual_is_a = (
                match.winner
                == prediction.player_a_name
            )

            probability_a = (
                float(prediction.player_a_probability)
                / 100.0
            )

            actual_value = (
                1.0
                if actual_is_a
                else 0.0
            )

            brier_score = (
                probability_a
                - actual_value
            ) ** 2

            actual_probability = (
                probability_a
                if actual_is_a
                else 1.0 - probability_a
            )

            records.append(
                (
                    prediction.predicted_winner
                    == match.winner,
                    round(brier_score, 6),
                    round(
                        PredictionValidationEngine._log_loss(
                            actual_probability
                        ),
                        6,
                    ),
                )
            )

        if not records:
            return V33WeightCandidateResult(
                weight=weight,
                accuracy=None,
                brier_score=None,
                log_loss=None,
            )

        correct = sum(
            int(record[0])
            for record in records
        )

        return V33WeightCandidateResult(
            weight=weight,
            accuracy=round(
                correct / len(records) * 100,
                3,
            ),
            brier_score=round(
                sum(record[1] for record in records)
                / len(records),
                6,
            ),
            log_loss=round(
                sum(record[2] for record in records)
                / len(records),
                6,
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
