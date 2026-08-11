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
class V33WrongConsensusFeature:
    feature_name: str

    correct_supporting: int
    incorrect_supporting: int

    correct_average_support_strength: Optional[float]
    incorrect_average_support_strength: Optional[float]

    support_rate_correct: Optional[float]
    support_rate_incorrect: Optional[float]

    incorrect_minus_correct_support_rate: Optional[float]


@dataclass(frozen=True)
class V33WrongConsensusWindow:
    offset: int
    segment_matches: int
    high_agreement_matches: int

    correct_high_agreement: int
    incorrect_high_agreement: int

    high_agreement_accuracy: Optional[float]

    features: Tuple[
        V33WrongConsensusFeature,
        ...
    ]


@dataclass(frozen=True)
class V33WrongConsensusReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int
    agreement_lower: float

    windows_completed: int

    total_high_agreement_matches: int
    total_correct_high_agreement: int
    total_incorrect_high_agreement: int

    windows: Tuple[
        V33WrongConsensusWindow,
        ...
    ]


class CurrentMatchEnrichmentV33WrongConsensusService:
    """
    Read-only diagnostic for high-consensus low-history
    transparent-v3.3 predictions.

    Compare feature support patterns between correct and incorrect
    predictions where active feature agreement is at or above the
    configured threshold.

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
        agreement_lower: float = 80.0,
        competition_code: Optional[str] = "MODUS",
    ) -> V33WrongConsensusReport:
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

        if (
            agreement_lower < 0.0
            or agreement_lower > 100.0
        ):
            raise ValueError(
                "agreement_lower must be between 0 and 100."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                agreement_lower=agreement_lower,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33WrongConsensusReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            agreement_lower=agreement_lower,
            windows_completed=len(windows),
            total_high_agreement_matches=sum(
                item.high_agreement_matches
                for item in windows
            ),
            total_correct_high_agreement=sum(
                item.correct_high_agreement
                for item in windows
            ),
            total_incorrect_high_agreement=sum(
                item.incorrect_high_agreement
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
        agreement_lower,
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

        selected = []

        for match_id in match_ids:
            match = (
                db.query(Match)
                .filter(
                    Match.id == match_id
                )
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

                supporting = []
                opposing = 0

                for contribution in (
                    prediction.contributions
                ):
                    weighted = float(
                        contribution.weighted_score
                    )

                    if weighted == 0.0:
                        continue

                    supports = (
                        weighted > 0.0
                        if favourite_is_a
                        else weighted < 0.0
                    )

                    if supports:
                        supporting.append(
                            contribution
                        )
                    else:
                        opposing += 1

                active = (
                    len(supporting)
                    + opposing
                )

                agreement = (
                    len(supporting)
                    / active
                    * 100.0
                    if active
                    else 0.0
                )

                selected.append(
                    {
                        "correct": (
                            prediction.predicted_winner
                            == match.winner
                        ),
                        "agreement": agreement,
                        "supporting": tuple(
                            supporting
                        ),
                    }
                )

            except (ValueError, LookupError):
                continue

        high = tuple(
            item
            for item in selected
            if (
                item["agreement"]
                >= agreement_lower
            )
        )

        correct_rows = tuple(
            item
            for item in high
            if item["correct"]
        )

        incorrect_rows = tuple(
            item
            for item in high
            if not item["correct"]
        )

        feature_names = sorted({
            contribution.feature_name
            for item in high
            for contribution
            in item["supporting"]
        })

        features = tuple(
            self._feature_summary(
                feature_name,
                correct_rows,
                incorrect_rows,
            )
            for feature_name
            in feature_names
        )

        return V33WrongConsensusWindow(
            offset=offset,
            segment_matches=len(
                selected
            ),
            high_agreement_matches=len(
                high
            ),
            correct_high_agreement=len(
                correct_rows
            ),
            incorrect_high_agreement=len(
                incorrect_rows
            ),
            high_agreement_accuracy=(
                self._percentage(
                    len(correct_rows),
                    len(high),
                )
            ),
            features=features,
        )

    @classmethod
    def _feature_summary(
        cls,
        feature_name,
        correct_rows,
        incorrect_rows,
    ):
        correct_strengths = tuple(
            abs(
                float(
                    contribution.weighted_score
                )
            )
            for item in correct_rows
            for contribution
            in item["supporting"]
            if (
                contribution.feature_name
                == feature_name
            )
        )

        incorrect_strengths = tuple(
            abs(
                float(
                    contribution.weighted_score
                )
            )
            for item in incorrect_rows
            for contribution
            in item["supporting"]
            if (
                contribution.feature_name
                == feature_name
            )
        )

        correct_supporting = len(
            correct_strengths
        )

        incorrect_supporting = len(
            incorrect_strengths
        )

        support_rate_correct = (
            cls._percentage(
                correct_supporting,
                len(correct_rows),
            )
        )

        support_rate_incorrect = (
            cls._percentage(
                incorrect_supporting,
                len(incorrect_rows),
            )
        )

        return V33WrongConsensusFeature(
            feature_name=feature_name,
            correct_supporting=(
                correct_supporting
            ),
            incorrect_supporting=(
                incorrect_supporting
            ),
            correct_average_support_strength=(
                cls._average(
                    correct_strengths
                )
            ),
            incorrect_average_support_strength=(
                cls._average(
                    incorrect_strengths
                )
            ),
            support_rate_correct=(
                support_rate_correct
            ),
            support_rate_incorrect=(
                support_rate_incorrect
            ),
            incorrect_minus_correct_support_rate=(
                cls._difference(
                    support_rate_incorrect,
                    support_rate_correct,
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
