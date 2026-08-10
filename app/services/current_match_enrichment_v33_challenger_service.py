from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.model_performance_laboratory import (
    ModelPerformanceLaboratory,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33ChallengerConfiguration:
    name: str
    weights: Dict[str, float]


@dataclass(frozen=True)
class V33ChallengerResult:
    name: str
    accuracy: Optional[float]
    brier_score: Optional[float]
    log_loss: Optional[float]

    accuracy_change: Optional[float]
    brier_gain: Optional[float]
    log_loss_gain: Optional[float]

    accepted: bool


@dataclass(frozen=True)
class V33ChallengerReport:
    model_version: str

    offset: int
    limit: int
    matches_evaluated: int

    baseline: V33ChallengerResult

    challengers: Tuple[
        V33ChallengerResult,
        ...
    ]

    best_accepted_challenger: Optional[str]


class CurrentMatchEnrichmentV33ChallengerService:
    """
    Compare in-memory transparent-v3.3 challenger configurations
    against the unchanged production baseline.

    Historical evaluation is read-only. No challenger is registered
    globally and no production model weights are modified.
    """

    def compare(
        self,
        db: Session,
        *,
        challengers: Iterable[
            V33ChallengerConfiguration
        ],
        offset: int,
        limit: int,
        competition_code: Optional[str] = "MODUS",
    ) -> V33ChallengerReport:
        configurations = tuple(
            challengers
        )

        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if not configurations:
            raise ValueError(
                "Enter at least one challenger."
            )

        names = [
            str(item.name or "").strip()
            for item in configurations
        ]

        if any(
            not name
            for name in names
        ):
            raise ValueError(
                "Every challenger requires a name."
            )

        if len(names) != len(set(names)):
            raise ValueError(
                "Challenger names must be unique."
            )

        match_ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=offset,
                limit=limit,
            )
        )

        if not match_ids:
            raise ValueError(
                "No validation-eligible completed "
                "matches were selected."
            )

        baseline_engine = (
            TransparentPredictionEngineV33()
        )

        models = [
            (
                "baseline-v3.3",
                baseline_engine,
            )
        ]

        for configuration in configurations:
            models.append(
                (
                    configuration.name,
                    self._engine_with_weights(
                        baseline_engine,
                        configuration.weights,
                    ),
                )
            )

        registry = PredictionModelRegistry(
            models=models,
            default_model="baseline-v3.3",
        )

        laboratory = ModelPerformanceLaboratory(
            model_registry=registry,
        )

        comparison = laboratory.compare_models(
            db,
            model_names=(
                name
                for name, _engine in models
            ),
            match_ids=match_ids,
            competition_code=competition_code,
        )

        summaries = {
            item.model_name: item
            for item in comparison.summaries
        }

        baseline_summary = summaries[
            "baseline-v3.3"
        ]

        baseline = V33ChallengerResult(
            name="baseline-v3.3",
            accuracy=baseline_summary.accuracy,
            brier_score=(
                baseline_summary
                .average_brier_score
            ),
            log_loss=(
                baseline_summary
                .average_log_loss
            ),
            accuracy_change=0.0,
            brier_gain=0.0,
            log_loss_gain=0.0,
            accepted=False,
        )

        results = []

        for configuration in configurations:
            summary = summaries[
                configuration.name
            ]

            accuracy_change = self._difference(
                summary.accuracy,
                baseline.accuracy,
            )

            brier_gain = self._difference(
                baseline.brier_score,
                summary.average_brier_score,
            )

            log_loss_gain = self._difference(
                baseline.log_loss,
                summary.average_log_loss,
            )

            accepted = self._accepted(
                baseline=baseline,
                accuracy=summary.accuracy,
                brier_score=(
                    summary.average_brier_score
                ),
                log_loss=(
                    summary.average_log_loss
                ),
            )

            results.append(
                V33ChallengerResult(
                    name=configuration.name,
                    accuracy=summary.accuracy,
                    brier_score=(
                        summary.average_brier_score
                    ),
                    log_loss=(
                        summary.average_log_loss
                    ),
                    accuracy_change=(
                        accuracy_change
                    ),
                    brier_gain=brier_gain,
                    log_loss_gain=(
                        log_loss_gain
                    ),
                    accepted=accepted,
                )
            )

        accepted_results = [
            item
            for item in results
            if item.accepted
        ]

        accepted_results.sort(
            key=lambda item: (
                item.brier_score
                if item.brier_score is not None
                else float("inf"),
                item.log_loss
                if item.log_loss is not None
                else float("inf"),
                -(
                    item.accuracy
                    if item.accuracy is not None
                    else -1.0
                ),
                item.name,
            )
        )

        best = (
            accepted_results[0]
            if accepted_results
            else None
        )

        return V33ChallengerReport(
            model_version=(
                baseline_engine.MODEL_VERSION
            ),
            offset=offset,
            limit=limit,
            matches_evaluated=(
                baseline_summary.matches_evaluated
            ),
            baseline=baseline,
            challengers=tuple(results),
            best_accepted_challenger=(
                best.name
                if best is not None
                else None
            ),
        )

    @staticmethod
    def _engine_with_weights(
        baseline_engine,
        weights,
    ):
        requested = {
            str(name).strip():
            float(value)
            for name, value in weights.items()
        }

        known = {
            feature.name
            for feature in baseline_engine.features
        }

        unknown = (
            set(requested)
            - known
        )

        if unknown:
            raise ValueError(
                "Unknown v3.3 feature(s): "
                + ", ".join(
                    sorted(unknown)
                )
            )

        if any(
            value < 0
            for value in requested.values()
        ):
            raise ValueError(
                "Feature weights cannot be negative."
            )

        features = tuple(
            replace(
                feature,
                weight=requested[
                    feature.name
                ],
            )
            if feature.name in requested
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
    def _accepted(
        *,
        baseline,
        accuracy,
        brier_score,
        log_loss,
    ):
        if (
            baseline.brier_score is None
            or baseline.log_loss is None
            or brier_score is None
            or log_loss is None
        ):
            return False

        brier_improved = (
            brier_score
            < baseline.brier_score
        )

        log_loss_improved = (
            log_loss
            < baseline.log_loss
        )

        accuracy_safe = (
            baseline.accuracy is None
            or accuracy is None
            or accuracy
            >= baseline.accuracy - 2.0
        )

        return (
            brier_improved
            and log_loss_improved
            and accuracy_safe
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
