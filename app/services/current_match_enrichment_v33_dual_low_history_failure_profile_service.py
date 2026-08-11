from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33DualLowHistoryFeatureProfile:
    feature_name: str

    correct_support_rate: Optional[float]
    incorrect_support_rate: Optional[float]
    support_rate_gap: Optional[float]

    correct_average_weighted_score: Optional[float]
    incorrect_average_weighted_score: Optional[float]

    correct_average_absolute_weighted_score: Optional[float]
    incorrect_average_absolute_weighted_score: Optional[float]


@dataclass(frozen=True)
class V33DualLowHistoryMatchProfile:
    match_id: int

    history_a: int
    history_b: int

    predicted_winner: str
    favourite_probability: float
    confidence: float
    model_score: float

    correct: bool

    supporting_features: int
    opposing_features: int
    agreement_percentage: Optional[float]


@dataclass(frozen=True)
class V33DualLowHistoryFailureProfileReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_threshold: int

    matches_evaluated: int
    dual_low_history_matches: int

    correct_predictions: int
    incorrect_predictions: int
    accuracy: Optional[float]

    average_correct_probability: Optional[float]
    average_incorrect_probability: Optional[float]

    average_correct_confidence: Optional[float]
    average_incorrect_confidence: Optional[float]

    average_correct_agreement: Optional[float]
    average_incorrect_agreement: Optional[float]

    features: Tuple[
        V33DualLowHistoryFeatureProfile,
        ...
    ]

    matches: Tuple[
        V33DualLowHistoryMatchProfile,
        ...
    ]


class CurrentMatchEnrichmentV33DualLowHistoryFailureProfileService:
    """
    Read-only diagnostic for transparent-v3.3 predictions where
    both players have extremely low pre-match history.

    Correct and incorrect predictions are compared at match and
    feature-contribution level.

    No model behaviour is modified.
    """

    def __init__(
        self,
        *,
        snapshot_engine=None,
        prediction_engine=None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine
            or AdvancedHistoricalSnapshotEngine()
        )

        self.prediction_engine = (
            prediction_engine
            or TransparentPredictionEngineV33()
        )

    def analyse(
        self,
        db: Session,
        *,
        offsets: Iterable[int],
        window_size: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        competition_code: Optional[str] = "MODUS",
    ) -> V33DualLowHistoryFailureProfileReport:
        offsets = tuple(
            int(value)
            for value in offsets
        )

        if not offsets:
            raise ValueError(
                "Enter at least one window offset."
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero."
            )

        if probability_lower < 50.0:
            raise ValueError(
                "probability_lower cannot be below 50."
            )

        if probability_upper <= probability_lower:
            raise ValueError(
                "probability_upper must exceed probability_lower."
            )

        if probability_upper > 100.0:
            raise ValueError(
                "probability_upper cannot exceed 100."
            )

        if history_threshold <= 0:
            raise ValueError(
                "history_threshold must be greater than zero."
            )

        seen = set()
        selected = []
        evaluated = 0

        for offset in offsets:
            match_ids = (
                CurrentMatchEnrichmentV33ValidationService
                ._select_match_ids(
                    db,
                    offset=offset,
                    limit=window_size,
                )
            )

            for match_id in match_ids:
                if match_id in seen:
                    continue

                seen.add(match_id)

                match = (
                    db.query(Match)
                    .filter(Match.id == match_id)
                    .first()
                )

                if match is None:
                    continue

                try:
                    snapshot = (
                        self.snapshot_engine
                        .build_match_snapshot(
                            db,
                            match_id,
                            competition_code=competition_code,
                        )
                    )

                    prediction = (
                        self.prediction_engine
                        .predict(snapshot)
                    )

                    evaluated += 1

                    favourite_probability = max(
                        float(
                            prediction.player_a_probability
                        ),
                        float(
                            prediction.player_b_probability
                        ),
                    )

                    if not (
                        favourite_probability
                        >= probability_lower
                        and favourite_probability
                        < probability_upper
                    ):
                        continue

                    history_a = int(
                        snapshot.player_a
                        .advanced_features
                        .matches_available
                    )

                    history_b = int(
                        snapshot.player_b
                        .advanced_features
                        .matches_available
                    )

                    if not (
                        history_a < history_threshold
                        and history_b < history_threshold
                    ):
                        continue

                    favourite_is_a = (
                        prediction.player_a_probability
                        >= prediction.player_b_probability
                    )

                    supporting = 0
                    opposing = 0

                    contribution_rows = []

                    for contribution in (
                        prediction.contributions
                    ):
                        weighted = float(
                            contribution.weighted_score
                        )

                        supports = None

                        if weighted != 0.0:
                            supports = (
                                weighted > 0.0
                                if favourite_is_a
                                else weighted < 0.0
                            )

                            if supports:
                                supporting += 1
                            else:
                                opposing += 1

                        contribution_rows.append(
                            {
                                "feature_name": (
                                    contribution.feature_name
                                ),
                                "raw_edge": float(
                                    contribution.raw_edge
                                ),
                                "normalised_edge": float(
                                    contribution.normalised_edge
                                ),
                                "weighted_score": weighted,
                                "supports": supports,
                            }
                        )

                    active = (
                        supporting
                        + opposing
                    )

                    agreement = (
                        supporting
                        / active
                        * 100.0
                        if active
                        else None
                    )

                    correct = (
                        prediction.predicted_winner
                        == match.winner
                    )

                    selected.append(
                        {
                            "match_id": int(match_id),
                            "history_a": history_a,
                            "history_b": history_b,
                            "predicted_winner": (
                                prediction.predicted_winner
                            ),
                            "favourite_probability": (
                                favourite_probability
                            ),
                            "confidence": float(
                                prediction.confidence
                            ),
                            "model_score": float(
                                prediction.model_score
                            ),
                            "correct": correct,
                            "supporting": supporting,
                            "opposing": opposing,
                            "agreement": agreement,
                            "contributions": tuple(
                                contribution_rows
                            ),
                        }
                    )

                except (ValueError, LookupError):
                    continue

        correct_rows = tuple(
            item
            for item in selected
            if item["correct"]
        )

        incorrect_rows = tuple(
            item
            for item in selected
            if not item["correct"]
        )

        feature_names = sorted({
            contribution["feature_name"]
            for item in selected
            for contribution
            in item["contributions"]
        })

        features = tuple(
            self._feature_profile(
                feature_name,
                correct_rows,
                incorrect_rows,
            )
            for feature_name
            in feature_names
        )

        matches = tuple(
            V33DualLowHistoryMatchProfile(
                match_id=item["match_id"],
                history_a=item["history_a"],
                history_b=item["history_b"],
                predicted_winner=(
                    item["predicted_winner"]
                ),
                favourite_probability=round(
                    item["favourite_probability"],
                    3,
                ),
                confidence=round(
                    item["confidence"],
                    3,
                ),
                model_score=round(
                    item["model_score"],
                    6,
                ),
                correct=item["correct"],
                supporting_features=(
                    item["supporting"]
                ),
                opposing_features=(
                    item["opposing"]
                ),
                agreement_percentage=(
                    round(
                        item["agreement"],
                        3,
                    )
                    if item["agreement"]
                    is not None
                    else None
                ),
            )
            for item in selected
        )

        return V33DualLowHistoryFailureProfileReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_threshold=history_threshold,
            matches_evaluated=evaluated,
            dual_low_history_matches=len(
                selected
            ),
            correct_predictions=len(
                correct_rows
            ),
            incorrect_predictions=len(
                incorrect_rows
            ),
            accuracy=self._percentage(
                len(correct_rows),
                len(selected),
            ),
            average_correct_probability=(
                self._average(
                    item[
                        "favourite_probability"
                    ]
                    for item in correct_rows
                )
            ),
            average_incorrect_probability=(
                self._average(
                    item[
                        "favourite_probability"
                    ]
                    for item in incorrect_rows
                )
            ),
            average_correct_confidence=(
                self._average(
                    item["confidence"]
                    for item in correct_rows
                )
            ),
            average_incorrect_confidence=(
                self._average(
                    item["confidence"]
                    for item in incorrect_rows
                )
            ),
            average_correct_agreement=(
                self._average(
                    item["agreement"]
                    for item in correct_rows
                    if item["agreement"]
                    is not None
                )
            ),
            average_incorrect_agreement=(
                self._average(
                    item["agreement"]
                    for item in incorrect_rows
                    if item["agreement"]
                    is not None
                )
            ),
            features=features,
            matches=matches,
        )

    @classmethod
    def _feature_profile(
        cls,
        feature_name,
        correct_rows,
        incorrect_rows,
    ):
        correct = cls._feature_values(
            feature_name,
            correct_rows,
        )

        incorrect = cls._feature_values(
            feature_name,
            incorrect_rows,
        )

        correct_support_rate = (
            cls._percentage(
                correct["supporting"],
                correct["observations"],
            )
        )

        incorrect_support_rate = (
            cls._percentage(
                incorrect["supporting"],
                incorrect["observations"],
            )
        )

        return V33DualLowHistoryFeatureProfile(
            feature_name=feature_name,
            correct_support_rate=(
                correct_support_rate
            ),
            incorrect_support_rate=(
                incorrect_support_rate
            ),
            support_rate_gap=(
                cls._difference(
                    incorrect_support_rate,
                    correct_support_rate,
                )
            ),
            correct_average_weighted_score=(
                cls._average(
                    correct["weighted"]
                )
            ),
            incorrect_average_weighted_score=(
                cls._average(
                    incorrect["weighted"]
                )
            ),
            correct_average_absolute_weighted_score=(
                cls._average(
                    abs(value)
                    for value
                    in correct["weighted"]
                )
            ),
            incorrect_average_absolute_weighted_score=(
                cls._average(
                    abs(value)
                    for value
                    in incorrect["weighted"]
                )
            ),
        )

    @staticmethod
    def _feature_values(
        feature_name,
        rows,
    ):
        observations = 0
        supporting = 0
        weighted = []

        for item in rows:
            contribution = next(
                (
                    contribution
                    for contribution
                    in item["contributions"]
                    if contribution[
                        "feature_name"
                    ] == feature_name
                ),
                None,
            )

            if contribution is None:
                continue

            observations += 1

            if contribution["supports"] is True:
                supporting += 1

            weighted.append(
                float(
                    contribution[
                        "weighted_score"
                    ]
                )
            )

        return {
            "observations": observations,
            "supporting": supporting,
            "weighted": tuple(weighted),
        }

    @staticmethod
    def _average(values):
        values = tuple(
            float(value)
            for value in values
        )

        if not values:
            return None

        return round(
            sum(values)
            / len(values),
            6,
        )

    @staticmethod
    def _percentage(
        numerator,
        denominator,
    ):
        if not denominator:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )

    @staticmethod
    def _difference(
        left,
        right,
    ):
        if (
            left is None
            or right is None
        ):
            return None

        return round(
            float(left)
            - float(right),
            6,
        )
