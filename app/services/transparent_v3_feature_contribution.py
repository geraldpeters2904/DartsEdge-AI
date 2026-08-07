from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

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
class FeatureContributionScore:
    feature_name: str

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
class FeatureContributionReport:
    model_version: str
    offset: int
    matches_requested: int
    matches_evaluated: int

    baseline_accuracy: Optional[float]
    baseline_brier_score: Optional[float]
    baseline_log_loss: Optional[float]

    features: Tuple[
        FeatureContributionScore,
        ...
    ]


class TransparentV3FeatureContributionLaboratory:
    """
    Measure Transparent v3 feature importance by ablation.

    The baseline and every disabled-feature candidate receive exactly
    the same historical match IDs and advanced no-look-ahead snapshots.
    """

    def analyse(
        self,
        db: Session,
        *,
        offset: int = 1000,
        limit: int = 500,
        competition_code: Optional[str] = None,
    ) -> FeatureContributionReport:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
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

        baseline_engine = (
            TransparentPredictionEngineV3()
        )

        baseline = self._evaluate(
            db,
            engine=baseline_engine,
            match_ids=match_ids,
            competition_code=competition_code,
        )

        scores = []

        for feature_name in (
            baseline_engine.feature_names()
        ):
            candidate_engine = (
                self._without_feature_normalised(
                    baseline_engine,
                    feature_name,
                )
            )

            candidate = self._evaluate(
                db,
                engine=candidate_engine,
                match_ids=match_ids,
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

            importance_score = self._importance_score(
                accuracy_drop=accuracy_drop,
                brier_increase=brier_increase,
                log_loss_increase=log_loss_increase,
            )

            scores.append(
                FeatureContributionScore(
                    feature_name=feature_name,
                    baseline_accuracy=(
                        baseline.accuracy
                    ),
                    disabled_accuracy=(
                        candidate.accuracy
                    ),
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
                    log_loss_increase=(
                        log_loss_increase
                    ),
                    importance_score=(
                        importance_score
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

        return FeatureContributionReport(
            model_version=(
                baseline_engine.MODEL_VERSION
            ),
            offset=offset,
            matches_requested=limit,
            matches_evaluated=(
                baseline.matches_evaluated
            ),
            baseline_accuracy=(
                baseline.accuracy
            ),
            baseline_brier_score=(
                baseline.average_brier_score
            ),
            baseline_log_loss=(
                baseline.average_log_loss
            ),
            features=tuple(scores),
        )

    @staticmethod
    def _without_feature_normalised(
        engine: TransparentPredictionEngineV3,
        feature_name: str,
    ) -> TransparentPredictionEngineV3:
        """
        Remove one feature while preserving total model weight.

        Without normalisation, removing any feature shrinks the
        model score toward zero and can appear to improve probability
        metrics merely by making every prediction less confident.
        """

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

        remaining_total = sum(
            float(feature.weight)
            for feature in remaining
        )

        if remaining_total <= 0:
            raise ValueError(
                "Remaining feature weights must total more than zero."
            )

        scale = (
            original_total
            / remaining_total
        )

        from dataclasses import replace

        normalised = [
            replace(
                feature,
                weight=float(feature.weight) * scale,
            )
            for feature in remaining
        ]

        return TransparentPredictionEngineV3(
            features=normalised,
            logistic_strength=engine.logistic_strength,
        )

    @staticmethod
    def _evaluate(
        db: Session,
        *,
        engine: TransparentPredictionEngineV3,
        match_ids,
        competition_code: Optional[str],
    ):
        return PredictionValidationEngine(
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
    def _importance_score(
        *,
        accuracy_drop: Optional[float],
        brier_increase: Optional[float],
        log_loss_increase: Optional[float],
    ) -> float:
        """
        Positive means removing the feature made performance worse.

        Probability quality receives most of the weight because calibrated
        probabilities are central to future value-betting decisions.
        """

        accuracy_component = (
            (accuracy_drop or 0.0) / 100.0
        )

        return round(
            accuracy_component * 0.30
            + (brier_increase or 0.0) * 0.35
            + (log_loss_increase or 0.0) * 0.35,
            6,
        )
