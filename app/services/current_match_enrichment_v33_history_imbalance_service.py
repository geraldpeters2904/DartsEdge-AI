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
class V33HistoryImbalanceBand:
    band: str

    predictions: int
    correct: int
    accuracy: Optional[float]

    recent_win_rate_supporting: int
    recent_win_rate_supporting_correct: int

    recent_win_rate_support_rate: Optional[float]
    recent_win_rate_support_accuracy: Optional[float]

    average_recent_win_rate_support_strength: Optional[float]


@dataclass(frozen=True)
class V33HistoryImbalanceWindow:
    offset: int
    matches_evaluated: int
    low_history_matches: int

    bands: Tuple[
        V33HistoryImbalanceBand,
        ...
    ]


@dataclass(frozen=True)
class V33HistoryImbalanceReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    minimum_history_upper: int

    windows_completed: int
    total_low_history_matches: int

    windows: Tuple[
        V33HistoryImbalanceWindow,
        ...
    ]


class CurrentMatchEnrichmentV33HistoryImbalanceService:
    """
    Read-only diagnostic for low-history transparent-v3.3 matches.

    The analysis tests whether recent_win_rate reliability varies
    according to the gap between the two players' available
    pre-match history depths.

    No model weights or probabilities are modified.
    """

    HISTORY_GAP_BANDS = (
        (0, 2),
        (2, 5),
        (5, 10),
        (10, None),
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
        minimum_history_upper: int = 3,
        competition_code: Optional[str] = "MODUS",
    ) -> V33HistoryImbalanceReport:
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

        if minimum_history_upper <= 0:
            raise ValueError(
                "minimum_history_upper must be greater than zero."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                minimum_history_upper=minimum_history_upper,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33HistoryImbalanceReport(
            model_version=self.prediction_engine.MODEL_VERSION,
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            minimum_history_upper=minimum_history_upper,
            windows_completed=len(windows),
            total_low_history_matches=sum(
                item.low_history_matches
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
        minimum_history_upper,
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

                minimum_history = min(
                    history_a,
                    history_b,
                )

                if minimum_history >= minimum_history_upper:
                    continue

                history_gap = abs(
                    history_a - history_b
                )

                favourite_is_a = (
                    prediction.player_a_probability
                    >= prediction.player_b_probability
                )

                feature = next(
                    (
                        item
                        for item in prediction.contributions
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
                        "history_a": history_a,
                        "history_b": history_b,
                        "minimum_history": minimum_history,
                        "history_gap": history_gap,
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
            in self.HISTORY_GAP_BANDS
        )

        return V33HistoryImbalanceWindow(
            offset=offset,
            matches_evaluated=evaluated,
            low_history_matches=len(selected),
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
                item["history_gap"] >= lower
                and (
                    upper is None
                    or item["history_gap"] < upper
                )
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

        label = (
            f"{lower}+"
            if upper is None
            else f"{lower}-{upper - 1}"
        )

        return V33HistoryImbalanceBand(
            band=label,
            predictions=len(rows),
            correct=correct,
            accuracy=cls._percentage(
                correct,
                len(rows),
            ),
            recent_win_rate_supporting=len(
                supporting
            ),
            recent_win_rate_supporting_correct=(
                supporting_correct
            ),
            recent_win_rate_support_rate=(
                cls._percentage(
                    len(supporting),
                    len(rows),
                )
            ),
            recent_win_rate_support_accuracy=(
                cls._percentage(
                    supporting_correct,
                    len(supporting),
                )
            ),
            average_recent_win_rate_support_strength=(
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
