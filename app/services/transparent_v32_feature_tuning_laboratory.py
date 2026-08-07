from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
)
from app.services.transparent_prediction_engine_v32 import (
    TransparentPredictionEngineV32,
)


@dataclass(frozen=True)
class FeatureTuningMetric:
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
class FeatureTuningSplit:
    training_offset: int
    validation_offset: int

    training_winner: float
    accepted: bool

    validation_accuracy_change: Optional[float]
    validation_brier_gain: Optional[float]
    validation_log_loss_gain: Optional[float]


@dataclass(frozen=True)
class FeatureTuningRecommendation:
    feature_name: str
    current_weight: float

    consensus_weight: Optional[float]
    consensus_votes: int
    splits_completed: int
    consensus_percentage: float

    promotion_recommended: bool
    confidence: str
    reason: str

    splits: Tuple[
        FeatureTuningSplit,
        ...
    ]


@dataclass(frozen=True)
class FeatureTuningReport:
    model_version: str
    recommendations: Tuple[
        FeatureTuningRecommendation,
        ...
    ]


class TransparentV32FeatureTuningLaboratory:
    """
    Tune v3.2 features using repeated training and hold-out splits.

    The laboratory is read-only. It recommends weights but does not
    modify the registered model or source files.
    """

    DEFAULT_WEIGHT_GRIDS = {
        "overall_strength": (
            0.00,
            0.06,
            0.12,
            0.18,
            0.24,
        ),
        "recent_form": (
            0.00,
            0.03,
            0.06,
            0.09,
        ),
        "scoring_power": (
            0.08,
            0.10,
            0.12,
            0.15,
            0.18,
        ),
        "finishing_strength": (
            0.05,
            0.08,
            0.10,
            0.12,
            0.15,
        ),
        "maximums_strength": (
            0.00,
            0.03,
            0.05,
            0.08,
            0.10,
        ),
        "recent_win_rate": (
            0.00,
            0.03,
            0.06,
            0.10,
        ),
        "checkout_trend": (
            0.00,
            0.03,
            0.05,
            0.07,
            0.10,
        ),
        "deciding_strength": (
            0.00,
            0.03,
            0.06,
            0.09,
        ),
        "scoring_consistency": (
            0.00,
            0.01,
            0.02,
            0.03,
            0.04,
            0.05,
            0.07,
            0.10,
        ),
    }

    def tune(
        self,
        db: Session,
        *,
        feature_names: Optional[
            Iterable[str]
        ] = None,
        training_offsets: Iterable[int] = (
            500,
            1000,
            1500,
        ),
        validation_offsets: Iterable[int] = (
            2000,
            2500,
            3000,
        ),
        training_limit: int = 500,
        validation_limit: int = 500,
        minimum_consensus: float = 0.67,
        competition_code: Optional[str] = None,
    ) -> FeatureTuningReport:
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

        if training_limit <= 0:
            raise ValueError(
                "training_limit must be greater than zero."
            )

        if validation_limit <= 0:
            raise ValueError(
                "validation_limit must be greater than zero."
            )

        if not 0 < minimum_consensus <= 1:
            raise ValueError(
                "minimum_consensus must be above "
                "zero and no greater than one."
            )

        baseline_engine = (
            TransparentPredictionEngineV32()
        )

        selected = tuple(
            feature_names
            if feature_names is not None
            else baseline_engine.feature_names()
        )

        unknown = (
            set(selected)
            - set(
                baseline_engine.feature_names()
            )
        )

        if unknown:
            raise ValueError(
                "Unknown v3.2 feature(s): "
                + ", ".join(sorted(unknown))
            )

        recommendations = tuple(
            self._tune_feature(
                db,
                baseline_engine=baseline_engine,
                feature_name=feature_name,
                candidate_weights=(
                    self.DEFAULT_WEIGHT_GRIDS[
                        feature_name
                    ]
                ),
                training_offsets=training,
                validation_offsets=validation,
                training_limit=training_limit,
                validation_limit=validation_limit,
                minimum_consensus=minimum_consensus,
                competition_code=competition_code,
            )
            for feature_name in selected
        )

        return FeatureTuningReport(
            model_version=(
                baseline_engine.MODEL_VERSION
            ),
            recommendations=(
                recommendations
            ),
        )

    def _tune_feature(
        self,
        db: Session,
        *,
        baseline_engine: (
            TransparentPredictionEngineV32
        ),
        feature_name: str,
        candidate_weights,
        training_offsets,
        validation_offsets,
        training_limit: int,
        validation_limit: int,
        minimum_consensus: float,
        competition_code: Optional[str],
    ) -> FeatureTuningRecommendation:
        current_weight = self._weight(
            baseline_engine,
            feature_name,
        )

        candidates = tuple(
            sorted({
                round(
                    float(value),
                    6,
                )
                for value in (
                    *candidate_weights,
                    current_weight,
                )
            })
        )

        split_results = []

        for (
            training_offset,
            validation_offset,
        ) in zip(
            training_offsets,
            validation_offsets,
        ):
            training_ids = (
                self._select_match_ids(
                    db,
                    offset=training_offset,
                    limit=training_limit,
                )
            )
            validation_ids = (
                self._select_match_ids(
                    db,
                    offset=validation_offset,
                    limit=validation_limit,
                )
            )

            if not training_ids:
                raise ValueError(
                    "No training matches were "
                    f"selected at offset "
                    f"{training_offset}."
                )

            if not validation_ids:
                raise ValueError(
                    "No validation matches were "
                    f"selected at offset "
                    f"{validation_offset}."
                )

            if (
                set(training_ids)
                & set(validation_ids)
            ):
                raise ValueError(
                    "Training and validation "
                    "match sets overlap."
                )

            training_metrics = tuple(
                self._evaluate(
                    db,
                    engine=self._with_weight(
                        baseline_engine,
                        feature_name,
                        weight,
                    ),
                    match_ids=training_ids,
                    competition_code=(
                        competition_code
                    ),
                    weight=weight,
                )
                for weight in candidates
            )

            training_winner = min(
                training_metrics,
                key=lambda item: (
                    item.ranking_key()
                ),
            )

            validation_baseline = (
                self._evaluate(
                    db,
                    engine=baseline_engine,
                    match_ids=validation_ids,
                    competition_code=(
                        competition_code
                    ),
                    weight=current_weight,
                )
            )

            validation_candidate = (
                self._evaluate(
                    db,
                    engine=self._with_weight(
                        baseline_engine,
                        feature_name,
                        training_winner.weight,
                    ),
                    match_ids=validation_ids,
                    competition_code=(
                        competition_code
                    ),
                    weight=(
                        training_winner.weight
                    ),
                )
            )

            accepted = (
                training_winner.weight
                != current_weight
                and (
                    validation_candidate
                    .ranking_key()
                    < validation_baseline
                    .ranking_key()
                )
            )

            split_results.append(
                FeatureTuningSplit(
                    training_offset=(
                        training_offset
                    ),
                    validation_offset=(
                        validation_offset
                    ),
                    training_winner=(
                        training_winner.weight
                    ),
                    accepted=accepted,
                    validation_accuracy_change=(
                        self._difference(
                            validation_candidate
                            .accuracy,
                            validation_baseline
                            .accuracy,
                        )
                    ),
                    validation_brier_gain=(
                        self._difference(
                            validation_baseline
                            .brier_score,
                            validation_candidate
                            .brier_score,
                        )
                    ),
                    validation_log_loss_gain=(
                        self._difference(
                            validation_baseline
                            .log_loss,
                            validation_candidate
                            .log_loss,
                        )
                    ),
                )
            )

        votes: Dict[float, int] = {}

        for split in split_results:
            if not split.accepted:
                continue

            weight = round(
                split.training_winner,
                6,
            )

            votes[weight] = (
                votes.get(weight, 0)
                + 1
            )

        consensus_weight = None
        consensus_votes = 0

        if votes:
            (
                consensus_weight,
                consensus_votes,
            ) = max(
                votes.items(),
                key=lambda item: (
                    item[1],
                    -abs(
                        item[0]
                        - current_weight
                    ),
                ),
            )

        split_count = len(split_results)

        consensus_fraction = (
            consensus_votes
            / split_count
            if split_count
            else 0.0
        )

        promote = (
            consensus_weight is not None
            and consensus_weight
            != current_weight
            and consensus_fraction
            >= minimum_consensus
        )

        if promote:
            reason = (
                f"Weight "
                f"{consensus_weight:.6f} "
                f"was accepted on "
                f"{consensus_votes}/"
                f"{split_count} hold-out "
                "splits."
            )
        elif not votes:
            reason = (
                "No candidate consistently "
                "improved hold-out results."
            )
        else:
            reason = (
                f"The leading candidate "
                f"received "
                f"{consensus_votes}/"
                f"{split_count} votes, "
                "below the required "
                "consensus."
            )

        return FeatureTuningRecommendation(
            feature_name=feature_name,
            current_weight=current_weight,
            consensus_weight=(
                consensus_weight
            ),
            consensus_votes=(
                consensus_votes
            ),
            splits_completed=split_count,
            consensus_percentage=round(
                consensus_fraction
                * 100.0,
                3,
            ),
            promotion_recommended=promote,
            confidence=self._confidence(
                consensus_fraction
            ),
            reason=reason,
            splits=tuple(split_results),
        )

    @staticmethod
    def _with_weight(
        engine: TransparentPredictionEngineV32,
        feature_name: str,
        weight: float,
    ) -> TransparentPredictionEngineV32:
        found = False
        updated = []

        for feature in engine.features:
            if feature.name == feature_name:
                updated.append(
                    replace(
                        feature,
                        weight=float(weight),
                    )
                )
                found = True
            else:
                updated.append(feature)

        if not found:
            raise ValueError(
                f"Unknown v3.2 feature: "
                f"{feature_name}."
            )

        return TransparentPredictionEngineV32(
            features=updated,
            logistic_strength=(
                engine.logistic_strength
            ),
        )

    @staticmethod
    def _weight(
        engine,
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
        engine,
        match_ids,
        competition_code,
        weight,
    ) -> FeatureTuningMetric:
        report = PredictionValidationEngine(
            snapshot_engine=(
                AdvancedHistoricalSnapshotEngine()
            ),
            prediction_engine=engine,
        ).validate_matches(
            db,
            match_ids=match_ids,
            competition_code=(
                competition_code
            ),
            include_records=False,
        )

        return FeatureTuningMetric(
            weight=float(weight),
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
        fraction: float,
    ) -> str:
        if fraction >= 1.0:
            return "high"

        if fraction >= 0.67:
            return "moderate"

        if fraction > 0:
            return "low"

        return "none"
