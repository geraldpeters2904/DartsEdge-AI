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
class V33RecentWinRateHistoryBand:
    band: str

    predictions: int
    correct: int
    accuracy: Optional[float]

    feature_supporting: int
    feature_supporting_correct: int

    feature_support_rate: Optional[float]
    feature_support_accuracy: Optional[float]

    average_support_strength: Optional[float]


@dataclass(frozen=True)
class V33RecentWinRateHistoryWindow:
    offset: int
    matches_evaluated: int
    segment_matches: int

    bands: Tuple[
        V33RecentWinRateHistoryBand,
        ...
    ]


@dataclass(frozen=True)
class V33RecentWinRateHistoryReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float

    windows_completed: int
    total_segment_matches: int

    windows: Tuple[
        V33RecentWinRateHistoryWindow,
        ...
    ]


class CurrentMatchEnrichmentV33RecentWinRateHistoryService:
    """
    Read-only diagnostic for recent_win_rate reliability by
    minimum pre-match history depth.

    The analysis is restricted to the configured favourite
    probability segment and does not modify v3.3.
    """

    HISTORY_BANDS = (
        (0, 3),
        (3, 5),
        (5, 7),
        (7, 10),
    )

    FEATURE_NAME = "recent_win_rate"

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
        competition_code: Optional[str] = "MODUS",
    ) -> V33RecentWinRateHistoryReport:
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

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33RecentWinRateHistoryReport(
            model_version=self.prediction_engine.MODEL_VERSION,
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
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
                    float(prediction.player_a_probability),
                    float(prediction.player_b_probability),
                )

                if not (
                    favourite_probability >= probability_lower
                    and favourite_probability < probability_upper
                ):
                    continue

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

                if minimum_history >= 10:
                    continue

                favourite_is_a = (
                    prediction.player_a_probability
                    >= prediction.player_b_probability
                )

                feature = next(
                    (
                        item
                        for item
                        in prediction.contributions
                        if item.feature_name
                        == self.FEATURE_NAME
                    ),
                    None,
                )

                supports = False
                support_strength = None

                if feature is not None:
                    weighted = float(
                        feature.weighted_score
                    )

                    if weighted != 0.0:
                        supports = (
                            weighted > 0.0
                            if favourite_is_a
                            else weighted < 0.0
                        )

                        if supports:
                            support_strength = abs(
                                weighted
                            )

                selected.append(
                    {
                        "minimum_history": minimum_history,
                        "correct": (
                            prediction.predicted_winner
                            == match.winner
                        ),
                        "supports": supports,
                        "support_strength": support_strength,
                    }
                )

            except (ValueError, LookupError):
                continue

        bands = tuple(
            self._build_band(
                selected,
                lower=lower,
                upper=upper,
            )
            for lower, upper
            in self.HISTORY_BANDS
        )

        return V33RecentWinRateHistoryWindow(
            offset=offset,
            matches_evaluated=evaluated,
            segment_matches=len(selected),
            bands=bands,
        )

    @classmethod
    def _build_band(
        cls,
        selected,
        *,
        lower,
        upper,
    ):
        rows = tuple(
            item
            for item in selected
            if (
                item["minimum_history"] >= lower
                and item["minimum_history"] < upper
            )
        )

        correct = sum(
            int(item["correct"])
            for item in rows
        )

        supporting = tuple(
            item
            for item in rows
            if item["supports"]
        )

        supporting_correct = sum(
            int(item["correct"])
            for item in supporting
        )

        strengths = tuple(
            item["support_strength"]
            for item in supporting
            if item["support_strength"]
            is not None
        )

        return V33RecentWinRateHistoryBand(
            band=(
                f"{lower}-{upper - 1}"
            ),
            predictions=len(rows),
            correct=correct,
            accuracy=cls._percentage(
                correct,
                len(rows),
            ),
            feature_supporting=len(
                supporting
            ),
            feature_supporting_correct=(
                supporting_correct
            ),
            feature_support_rate=(
                cls._percentage(
                    len(supporting),
                    len(rows),
                )
            ),
            feature_support_accuracy=(
                cls._percentage(
                    supporting_correct,
                    len(supporting),
                )
            ),
            average_support_strength=(
                cls._average(
                    strengths
                )
            ),
        )

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
        if not denominator:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )
