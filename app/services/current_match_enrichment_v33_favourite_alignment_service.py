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
class V33FavouriteFeatureAlignment:
    feature_name: str

    observations: int

    supporting: int
    opposing: int
    neutral: int

    supporting_correct: int
    supporting_incorrect: int

    opposing_correct: int
    opposing_incorrect: int

    support_percentage: Optional[float]
    support_accuracy: Optional[float]
    opposition_accuracy: Optional[float]

    average_support_strength: Optional[float]
    average_opposition_strength: Optional[float]


@dataclass(frozen=True)
class V33FavouriteAlignmentWindow:
    offset: int
    matches_evaluated: int
    segment_matches: int
    correct: int
    accuracy: Optional[float]

    feature_alignments: Tuple[
        V33FavouriteFeatureAlignment,
        ...
    ]


@dataclass(frozen=True)
class V33FavouriteAlignmentReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int

    windows_completed: int
    total_segment_matches: int

    windows: Tuple[
        V33FavouriteAlignmentWindow,
        ...
    ]


class CurrentMatchEnrichmentV33FavouriteAlignmentService:
    """
    Read-only diagnostic showing whether individual v3.3 feature
    contributions support or oppose the model's predicted favourite.

    Feature alignment is also separated by whether the overall model
    prediction was correct.

    No model weights or probabilities are modified.
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
        history_upper: int = 10,
        competition_code: Optional[str] = "MODUS",
    ) -> V33FavouriteAlignmentReport:
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

        if history_upper <= 0:
            raise ValueError(
                "history_upper must be greater than zero."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33FavouriteAlignmentReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            windows_completed=len(windows),
            total_segment_matches=sum(
                item.segment_matches
                for item in windows
            ),
            windows=windows,
        )

    def _analyse_window(
        self,
        db,
        *,
        offset,
        window_size,
        probability_lower,
        probability_upper,
        history_upper,
        competition_code,
    ):
        match_ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=offset,
                limit=window_size,
            )
        )

        evaluated = 0
        selected = []

        for match_id in match_ids:
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

                minimum_history = min(
                    int(
                        snapshot.player_a
                        .advanced_features
                        .matches_available
                    ),
                    int(
                        snapshot.player_b
                        .advanced_features
                        .matches_available
                    ),
                )

                if not (
                    favourite_probability
                    >= probability_lower
                    and favourite_probability
                    < probability_upper
                    and minimum_history
                    < history_upper
                ):
                    continue

                favourite_is_a = (
                    prediction.player_a_probability
                    >= prediction.player_b_probability
                )

                correct = (
                    prediction.predicted_winner
                    == match.winner
                )

                selected.append(
                    {
                        "correct": correct,
                        "favourite_is_a": favourite_is_a,
                        "contributions": (
                            prediction.contributions
                        ),
                    }
                )

            except (ValueError, LookupError):
                continue

        correct = sum(
            int(item["correct"])
            for item in selected
        )

        return V33FavouriteAlignmentWindow(
            offset=offset,
            matches_evaluated=evaluated,
            segment_matches=len(selected),
            correct=correct,
            accuracy=(
                self._percentage(
                    correct,
                    len(selected),
                )
                if selected
                else None
            ),
            feature_alignments=(
                self._feature_alignments(
                    selected
                )
            ),
        )

    @classmethod
    def _feature_alignments(
        cls,
        selected,
    ):
        feature_names = sorted({
            contribution.feature_name
            for item in selected
            for contribution
            in item["contributions"]
        })

        results = []

        for feature_name in feature_names:
            supporting = []
            opposing = []
            neutral = 0

            supporting_correct = 0
            supporting_incorrect = 0

            opposing_correct = 0
            opposing_incorrect = 0

            observations = 0

            for item in selected:
                contribution = next(
                    (
                        contribution
                        for contribution
                        in item["contributions"]
                        if contribution.feature_name
                        == feature_name
                    ),
                    None,
                )

                if contribution is None:
                    continue

                observations += 1

                weighted = float(
                    contribution.weighted_score
                )

                if weighted == 0.0:
                    neutral += 1
                    continue

                supports_favourite = (
                    weighted > 0.0
                    if item["favourite_is_a"]
                    else weighted < 0.0
                )

                if supports_favourite:
                    supporting.append(
                        abs(weighted)
                    )

                    if item["correct"]:
                        supporting_correct += 1
                    else:
                        supporting_incorrect += 1

                else:
                    opposing.append(
                        abs(weighted)
                    )

                    if item["correct"]:
                        opposing_correct += 1
                    else:
                        opposing_incorrect += 1

            support_total = (
                supporting_correct
                + supporting_incorrect
            )

            opposition_total = (
                opposing_correct
                + opposing_incorrect
            )

            results.append(
                V33FavouriteFeatureAlignment(
                    feature_name=feature_name,
                    observations=observations,
                    supporting=support_total,
                    opposing=opposition_total,
                    neutral=neutral,
                    supporting_correct=(
                        supporting_correct
                    ),
                    supporting_incorrect=(
                        supporting_incorrect
                    ),
                    opposing_correct=(
                        opposing_correct
                    ),
                    opposing_incorrect=(
                        opposing_incorrect
                    ),
                    support_percentage=(
                        cls._percentage(
                            support_total,
                            observations,
                        )
                        if observations
                        else None
                    ),
                    support_accuracy=(
                        cls._percentage(
                            supporting_correct,
                            support_total,
                        )
                        if support_total
                        else None
                    ),
                    opposition_accuracy=(
                        cls._percentage(
                            opposing_correct,
                            opposition_total,
                        )
                        if opposition_total
                        else None
                    ),
                    average_support_strength=(
                        cls._average(
                            supporting
                        )
                    ),
                    average_opposition_strength=(
                        cls._average(
                            opposing
                        )
                    ),
                )
            )

        return tuple(results)

    @staticmethod
    def _average(values):
        values = tuple(
            float(value)
            for value in values
        )

        if not values:
            return None

        return round(
            sum(values) / len(values),
            6,
        )

    @staticmethod
    def _percentage(
        numerator,
        denominator,
    ):
        if denominator == 0:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )
