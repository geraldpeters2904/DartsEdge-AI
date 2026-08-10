from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

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
class V33HistoryDepthSegment:
    dimension: str
    segment: str

    predictions: int
    correct: int

    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]


@dataclass(frozen=True)
class V33HistoryDepthReport:
    model_version: str
    competition_code: Optional[str]

    offset: int
    limit: int
    matches_evaluated: int
    matches_skipped: int

    minimum_history_segments: Tuple[
        V33HistoryDepthSegment,
        ...
    ]

    combined_history_segments: Tuple[
        V33HistoryDepthSegment,
        ...
    ]


@dataclass(frozen=True)
class _HistoryDepthRecord:
    correct: bool
    brier_score: float
    log_loss: float

    minimum_history: int
    combined_history: int


class CurrentMatchEnrichmentV33HistoryDepthService:
    """
    Read-only transparent-v3.3 history-depth diagnostics.

    History counts come directly from each player's pre-match
    AdvancedPlayerFeatureProfile, preserving the historical
    snapshot engine's no-look-ahead guarantee.
    """

    MINIMUM_HISTORY_BANDS = (
        (0, 5),
        (5, 10),
        (10, 20),
        (20, 40),
        (40, None),
    )

    COMBINED_HISTORY_BANDS = (
        (0, 10),
        (10, 20),
        (20, 40),
        (40, 80),
        (80, None),
    )

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
        offset: int = 0,
        limit: int = 500,
        competition_code: Optional[str] = "MODUS",
    ) -> V33HistoryDepthReport:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        match_ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=offset,
                limit=limit,
            )
        )

        records = []
        skipped = 0

        for match_id in match_ids:
            match = (
                db.query(Match)
                .filter(Match.id == match_id)
                .first()
            )

            if match is None:
                skipped += 1
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

                predicted_correct = (
                    prediction.predicted_winner
                    == match.winner
                )

                records.append(
                    _HistoryDepthRecord(
                        correct=predicted_correct,
                        brier_score=round(
                            (
                                probability_a
                                - float(actual_a)
                            ) ** 2,
                            6,
                        ),
                        log_loss=self._log_loss(
                            actual_probability
                        ),
                        minimum_history=min(
                            history_a,
                            history_b,
                        ),
                        combined_history=(
                            history_a
                            + history_b
                        ),
                    )
                )

            except (ValueError, LookupError):
                skipped += 1

        return V33HistoryDepthReport(
            model_version=(
                self.prediction_engine
                .MODEL_VERSION
            ),
            competition_code=competition_code,
            offset=offset,
            limit=limit,
            matches_evaluated=len(records),
            matches_skipped=skipped,
            minimum_history_segments=tuple(
                self._segment(
                    records,
                    dimension="minimum_history",
                    lower=lower,
                    upper=upper,
                    value_getter=lambda item:
                        item.minimum_history,
                )
                for lower, upper
                in self.MINIMUM_HISTORY_BANDS
            ),
            combined_history_segments=tuple(
                self._segment(
                    records,
                    dimension="combined_history",
                    lower=lower,
                    upper=upper,
                    value_getter=lambda item:
                        item.combined_history,
                )
                for lower, upper
                in self.COMBINED_HISTORY_BANDS
            ),
        )

    @classmethod
    def _segment(
        cls,
        records,
        *,
        dimension,
        lower,
        upper,
        value_getter,
    ):
        selected = tuple(
            record
            for record in records
            if (
                value_getter(record)
                >= lower
                and (
                    upper is None
                    or value_getter(record)
                    < upper
                )
            )
        )

        label = (
            f"{lower}+"
            if upper is None
            else f"{lower}-{upper - 1}"
        )

        predictions = len(selected)

        correct = sum(
            int(item.correct)
            for item in selected
        )

        return V33HistoryDepthSegment(
            dimension=dimension,
            segment=label,
            predictions=predictions,
            correct=correct,
            accuracy=(
                cls._percentage(
                    correct,
                    predictions,
                )
                if predictions
                else None
            ),
            average_brier_score=(
                cls._average(
                    item.brier_score
                    for item in selected
                )
            ),
            average_log_loss=(
                cls._average(
                    item.log_loss
                    for item in selected
                )
            ),
        )

    @staticmethod
    def _average(values):
        available = [
            float(value)
            for value in values
            if value is not None
        ]

        if not available:
            return None

        return round(
            sum(available)
            / len(available),
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
        from math import log

        clipped = min(
            max(
                float(actual_probability),
                1e-9,
            ),
            1.0 - 1e-9,
        )

        return round(
            -log(clipped),
            6,
        )
