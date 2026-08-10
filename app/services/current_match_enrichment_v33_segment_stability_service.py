from __future__ import annotations

from dataclasses import dataclass
from math import log
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
class V33SegmentStabilityWindow:
    offset: int
    matches_evaluated: int
    segment_matches: int
    correct: int

    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]


@dataclass(frozen=True)
class V33SegmentStabilityReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_lower: int
    history_upper: Optional[int]

    windows_completed: int
    windows_with_evidence: int

    total_matches_evaluated: int
    total_segment_matches: int

    weighted_accuracy: Optional[float]
    weighted_brier_score: Optional[float]
    weighted_log_loss: Optional[float]

    windows_below_50_accuracy: int
    windows_below_60_accuracy: int

    windows: Tuple[
        V33SegmentStabilityWindow,
        ...
    ]


class CurrentMatchEnrichmentV33SegmentStabilityService:
    """
    Read-only cross-window stability analysis for a joint
    transparent-v3.3 probability/history segment.

    Each window uses the normal historical no-look-ahead snapshot
    path. History depth is the minimum pre-match history available
    across the two players.
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
        history_lower: int = 20,
        history_upper: Optional[int] = 40,
        competition_code: Optional[str] = "MODUS",
    ) -> V33SegmentStabilityReport:
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

        if probability_lower < 50:
            raise ValueError(
                "probability_lower cannot be below 50."
            )

        if probability_upper <= probability_lower:
            raise ValueError(
                "probability_upper must exceed probability_lower."
            )

        if probability_upper > 100:
            raise ValueError(
                "probability_upper cannot exceed 100."
            )

        if history_lower < 0:
            raise ValueError(
                "history_lower cannot be negative."
            )

        if (
            history_upper is not None
            and history_upper <= history_lower
        ):
            raise ValueError(
                "history_upper must exceed history_lower."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_lower=history_lower,
                history_upper=history_upper,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        evidence = tuple(
            window
            for window in windows
            if window.segment_matches > 0
        )

        total_segment_matches = sum(
            window.segment_matches
            for window in evidence
        )

        total_correct = sum(
            window.correct
            for window in evidence
        )

        return V33SegmentStabilityReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_lower=history_lower,
            history_upper=history_upper,
            windows_completed=len(windows),
            windows_with_evidence=len(evidence),
            total_matches_evaluated=sum(
                window.matches_evaluated
                for window in windows
            ),
            total_segment_matches=total_segment_matches,
            weighted_accuracy=(
                self._percentage(
                    total_correct,
                    total_segment_matches,
                )
                if total_segment_matches
                else None
            ),
            weighted_brier_score=(
                self._weighted_metric(
                    evidence,
                    "average_brier_score",
                )
            ),
            weighted_log_loss=(
                self._weighted_metric(
                    evidence,
                    "average_log_loss",
                )
            ),
            windows_below_50_accuracy=sum(
                1
                for window in evidence
                if (
                    window.accuracy is not None
                    and window.accuracy < 50.0
                )
            ),
            windows_below_60_accuracy=sum(
                1
                for window in evidence
                if (
                    window.accuracy is not None
                    and window.accuracy < 60.0
                )
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
        history_lower,
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

        selected = []
        evaluated = 0

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

                in_probability = (
                    favourite_probability
                    >= probability_lower
                    and favourite_probability
                    < probability_upper
                )

                in_history = (
                    minimum_history
                    >= history_lower
                    and (
                        history_upper is None
                        or minimum_history
                        < history_upper
                    )
                )

                if not (
                    in_probability
                    and in_history
                ):
                    continue

                actual_a = (
                    match.winner
                    == match.player_a
                )

                probability_a = (
                    float(
                        prediction
                        .player_a_probability
                    )
                    / 100.0
                )

                actual_probability = (
                    probability_a
                    if actual_a
                    else 1.0 - probability_a
                )

                selected.append(
                    (
                        prediction.predicted_winner
                        == match.winner,
                        (
                            probability_a
                            - float(actual_a)
                        ) ** 2,
                        self._log_loss(
                            actual_probability
                        ),
                    )
                )

            except (ValueError, LookupError):
                continue

        correct = sum(
            int(item[0])
            for item in selected
        )

        return V33SegmentStabilityWindow(
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
            average_brier_score=(
                self._average(
                    item[1]
                    for item in selected
                )
            ),
            average_log_loss=(
                self._average(
                    item[2]
                    for item in selected
                )
            ),
        )

    @staticmethod
    def _weighted_metric(
        windows,
        attribute,
    ):
        available = tuple(
            window
            for window in windows
            if getattr(
                window,
                attribute,
            ) is not None
        )

        denominator = sum(
            window.segment_matches
            for window in available
        )

        if denominator == 0:
            return None

        numerator = sum(
            float(
                getattr(
                    window,
                    attribute,
                )
            )
            * window.segment_matches
            for window in available
        )

        return round(
            numerator / denominator,
            6,
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
        if denominator == 0:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )

    @staticmethod
    def _log_loss(
        actual_probability,
    ):
        clipped = min(
            max(
                float(actual_probability),
                1e-9,
            ),
            1.0 - 1e-9,
        )

        return -log(clipped)
