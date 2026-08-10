from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33FeatureAblationScore:
    feature_name: str
    feature_weight: float

    baseline_accuracy: Optional[float]
    disabled_accuracy: Optional[float]
    accuracy_drop: Optional[float]

    baseline_brier_score: Optional[float]
    disabled_brier_score: Optional[float]
    brier_increase: Optional[float]

    baseline_log_loss: Optional[float]
    disabled_log_loss: Optional[float]
    log_loss_increase: Optional[float]

    importance_score: float

    @property
    def helpful(self) -> bool:
        return self.importance_score > 0

    @property
    def harmful(self) -> bool:
        return self.importance_score < 0


@dataclass(frozen=True)
class V33FeatureAblationReport:
    model_version: str
    competition_code: Optional[str]
    offset: int
    limit: int
    matches_evaluated: int

    baseline_accuracy: Optional[float]
    baseline_brier_score: Optional[float]
    baseline_log_loss: Optional[float]

    features: Tuple[V33FeatureAblationScore, ...]


class CurrentMatchEnrichmentV33FeatureAblationService:
    """
    Read-only feature ablation for transparent-v3.3.

    Every candidate is evaluated against the same deterministic
    historical match window. Removing an active feature re-normalises
    the remaining positive feature weights to preserve total model
    weight.

    Zero-weight features are reported but are not meaningfully
    ablated because they make no contribution to the baseline model.
    """

    def analyse(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 100,
        competition_code: Optional[str] = "MODUS",
    ) -> V33FeatureAblationReport:
        baseline_engine = TransparentPredictionEngineV33()

        baseline = self._validate(
            db,
            engine=baseline_engine,
            offset=offset,
            limit=limit,
            competition_code=competition_code,
        )

        scores = []

        for feature in baseline_engine.features:
            if float(feature.weight) <= 0:
                continue

            candidate_engine = (
                self._without_feature_normalised(
                    baseline_engine,
                    feature.name,
                )
            )

            candidate = self._validate(
                db,
                engine=candidate_engine,
                offset=offset,
                limit=limit,
                competition_code=competition_code,
            )

            accuracy_drop = self._difference(
                baseline.accuracy,
                candidate.accuracy,
            )
            brier_increase = self._difference(
                candidate.average_brier_score,
                baseline.average_brier_score,
            )
            log_loss_increase = self._difference(
                candidate.average_log_loss,
                baseline.average_log_loss,
            )

            scores.append(
                V33FeatureAblationScore(
                    feature_name=feature.name,
                    feature_weight=float(feature.weight),
                    baseline_accuracy=baseline.accuracy,
                    disabled_accuracy=candidate.accuracy,
                    accuracy_drop=accuracy_drop,
                    baseline_brier_score=(
                        baseline.average_brier_score
                    ),
                    disabled_brier_score=(
                        candidate.average_brier_score
                    ),
                    brier_increase=brier_increase,
                    baseline_log_loss=(
                        baseline.average_log_loss
                    ),
                    disabled_log_loss=(
                        candidate.average_log_loss
                    ),
                    log_loss_increase=log_loss_increase,
                    importance_score=self._importance_score(
                        accuracy_drop=accuracy_drop,
                        brier_increase=brier_increase,
                        log_loss_increase=log_loss_increase,
                    ),
                )
            )

        scores.sort(
            key=lambda item: (
                item.importance_score,
                item.accuracy_drop
                if item.accuracy_drop is not None
                else float("-inf"),
            ),
            reverse=True,
        )

        return V33FeatureAblationReport(
            model_version=baseline.model_version,
            competition_code=competition_code,
            offset=offset,
            limit=limit,
            matches_evaluated=baseline.matches_evaluated,
            baseline_accuracy=baseline.accuracy,
            baseline_brier_score=(
                baseline.average_brier_score
            ),
            baseline_log_loss=(
                baseline.average_log_loss
            ),
            features=tuple(scores),
        )

    @staticmethod
    def _validate(
        db,
        *,
        engine,
        offset,
        limit,
        competition_code,
    ):
        service = (
            CurrentMatchEnrichmentV33ValidationService(
                prediction_engine=engine,
            )
        )

        return service.validate(
            db,
            offset=offset,
            limit=limit,
            competition_code=competition_code,
        )

    @staticmethod
    def _without_feature_normalised(
        engine: TransparentPredictionEngineV33,
        feature_name: str,
    ) -> TransparentPredictionEngineV33:
        original_total = sum(
            float(feature.weight)
            for feature in engine.features
        )

        remaining = [
            feature
            for feature in engine.features
            if feature.name != feature_name
        ]

        if len(remaining) == len(engine.features):
            raise ValueError(
                f"Unknown prediction feature: {feature_name}."
            )

        removed = next(
            feature
            for feature in engine.features
            if feature.name == feature_name
        )

        if float(removed.weight) <= 0:
            raise ValueError(
                "Cannot meaningfully ablate a zero-weight feature."
            )

        remaining_total = sum(
            float(feature.weight)
            for feature in remaining
        )

        if remaining_total <= 0:
            raise ValueError(
                "Remaining feature weights must total more than zero."
            )

        scale = original_total / remaining_total

        normalised = tuple(
            replace(
                feature,
                weight=float(feature.weight) * scale,
            )
            for feature in remaining
        )

        return TransparentPredictionEngineV33(
            features=normalised,
            logistic_strength=engine.logistic_strength,
        )

    @staticmethod
    def _difference(left, right):
        if left is None or right is None:
            return None

        return round(
            float(left) - float(right),
            6,
        )

    @staticmethod
    def _importance_score(
        *,
        accuracy_drop,
        brier_increase,
        log_loss_increase,
    ) -> float:
        values = []

        if accuracy_drop is not None:
            values.append(float(accuracy_drop) / 100.0)

        if brier_increase is not None:
            values.append(float(brier_increase))

        if log_loss_increase is not None:
            values.append(float(log_loss_increase))

        if not values:
            return 0.0

        return round(
            sum(values) / len(values),
            6,
        )
