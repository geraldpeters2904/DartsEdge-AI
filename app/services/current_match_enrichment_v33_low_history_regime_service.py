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
class V33LowHistoryFeatureProfile:
    feature_name: str

    average_raw_edge: Optional[float]
    average_absolute_raw_edge: Optional[float]

    average_normalised_edge: Optional[float]
    average_absolute_normalised_edge: Optional[float]

    average_weighted_score: Optional[float]
    average_absolute_weighted_score: Optional[float]


@dataclass(frozen=True)
class V33LowHistoryRegimeWindow:
    offset: int

    matches_evaluated: int
    segment_matches: int
    correct: int

    accuracy: Optional[float]
    average_favourite_probability: Optional[float]
    average_minimum_history: Optional[float]

    feature_profiles: Tuple[
        V33LowHistoryFeatureProfile,
        ...
    ]


@dataclass(frozen=True)
class V33LowHistoryRegimeReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int

    windows_completed: int
    total_matches_evaluated: int
    total_segment_matches: int

    windows: Tuple[
        V33LowHistoryRegimeWindow,
        ...
    ]


class CurrentMatchEnrichmentV33LowHistoryRegimeService:
    """
    Read-only regime diagnostic for the low-history transparent-v3.3
    reliability segment.

    For each historical window, capture the actual feature
    contributions emitted by the active v3.3 prediction engine.

    This service does not modify model weights or probabilities.
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
    ) -> V33LowHistoryRegimeReport:
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

        return V33LowHistoryRegimeReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            windows_completed=len(windows),
            total_matches_evaluated=sum(
                item.matches_evaluated
                for item in windows
            ),
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

                favourite_probability = max(
                    float(
                        prediction
                        .player_a_probability
                    ),
                    float(
                        prediction
                        .player_b_probability
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

                selected.append(
                    {
                        "correct": (
                            prediction.predicted_winner
                            == match.winner
                        ),
                        "favourite_probability": (
                            favourite_probability
                        ),
                        "minimum_history": (
                            minimum_history
                        ),
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

        return V33LowHistoryRegimeWindow(
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
            average_favourite_probability=(
                self._average(
                    item["favourite_probability"]
                    for item in selected
                )
            ),
            average_minimum_history=(
                self._average(
                    item["minimum_history"]
                    for item in selected
                )
            ),
            feature_profiles=(
                self._feature_profiles(
                    selected
                )
            ),
        )

    @classmethod
    def _feature_profiles(
        cls,
        selected,
    ):
        feature_names = sorted({
            contribution.feature_name
            for item in selected
            for contribution
            in item["contributions"]
        })

        profiles = []

        for feature_name in feature_names:
            contributions = tuple(
                contribution
                for item in selected
                for contribution
                in item["contributions"]
                if contribution.feature_name
                == feature_name
            )

            profiles.append(
                V33LowHistoryFeatureProfile(
                    feature_name=feature_name,
                    average_raw_edge=cls._average(
                        item.raw_edge
                        for item in contributions
                    ),
                    average_absolute_raw_edge=(
                        cls._average(
                            abs(item.raw_edge)
                            for item in contributions
                        )
                    ),
                    average_normalised_edge=(
                        cls._average(
                            item.normalised_edge
                            for item in contributions
                        )
                    ),
                    average_absolute_normalised_edge=(
                        cls._average(
                            abs(
                                item.normalised_edge
                            )
                            for item in contributions
                        )
                    ),
                    average_weighted_score=(
                        cls._average(
                            item.weighted_score
                            for item in contributions
                        )
                    ),
                    average_absolute_weighted_score=(
                        cls._average(
                            abs(
                                item.weighted_score
                            )
                            for item in contributions
                        )
                    ),
                )
            )

        return tuple(profiles)

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
