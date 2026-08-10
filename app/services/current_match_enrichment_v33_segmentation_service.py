from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33PerformanceSegment:
    dimension: str
    segment: str

    predictions: int
    correct: int

    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]


@dataclass(frozen=True)
class V33PerformanceSegmentationReport:
    model_version: str
    competition_code: Optional[str]

    offset: int
    limit: int

    matches_evaluated: int

    overall_accuracy: Optional[float]
    overall_brier_score: Optional[float]
    overall_log_loss: Optional[float]

    probability_segments: Tuple[
        V33PerformanceSegment,
        ...
    ]

    confidence_segments: Tuple[
        V33PerformanceSegment,
        ...
    ]

    tournament_segments: Tuple[
        V33PerformanceSegment,
        ...
    ]

    stage_segments: Tuple[
        V33PerformanceSegment,
        ...
    ]


class CurrentMatchEnrichmentV33SegmentationService:
    """
    Read-only diagnostic segmentation for transparent-v3.3.

    The service evaluates one deterministic historical window and
    groups the resulting validation records by prediction strength,
    model confidence, tournament and stage.

    No model weights or warehouse data are modified.
    """

    PROBABILITY_BANDS = (
        (50, 55),
        (55, 60),
        (60, 65),
        (65, 70),
        (70, 80),
        (80, 101),
    )

    CONFIDENCE_BANDS = (
        (0, 40),
        (40, 60),
        (60, 80),
        (80, 101),
    )

    def __init__(
        self,
        *,
        snapshot_engine=None,
        prediction_engine=None,
    ) -> None:
        self.prediction_engine = (
            prediction_engine
            or TransparentPredictionEngineV33()
        )

        self.snapshot_engine = (
            snapshot_engine
            or AdvancedHistoricalSnapshotEngine()
        )

    def analyse(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 500,
        competition_code: Optional[str] = "MODUS",
    ) -> V33PerformanceSegmentationReport:
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

        validator_kwargs = {
            "prediction_engine":
                self.prediction_engine,
        }

        if self.snapshot_engine is not None:
            validator_kwargs[
                "snapshot_engine"
            ] = self.snapshot_engine

        validator = PredictionValidationEngine(
            **validator_kwargs
        )

        validation = validator.validate_matches(
            db,
            match_ids=match_ids,
            competition_code=competition_code,
            include_records=True,
        )

        records = tuple(
            validation.records
        )

        probability_segments = tuple(
            self._numeric_segment(
                records,
                dimension="favourite_probability",
                lower=lower,
                upper=upper,
                value_getter=lambda record:
                    record.favourite_probability,
            )
            for lower, upper
            in self.PROBABILITY_BANDS
        )

        confidence_segments = tuple(
            self._numeric_segment(
                records,
                dimension="confidence",
                lower=lower,
                upper=upper,
                value_getter=lambda record:
                    record.confidence,
            )
            for lower, upper
            in self.CONFIDENCE_BANDS
        )

        tournament_segments = (
            self._categorical_segments(
                records,
                dimension="tournament",
                value_getter=lambda record:
                    record.tournament
                    or "Unknown",
            )
        )

        stage_segments = (
            self._categorical_segments(
                records,
                dimension="stage",
                value_getter=lambda record:
                    record.stage
                    or "Unknown",
            )
        )

        return V33PerformanceSegmentationReport(
            model_version=(
                validation.model_version
            ),
            competition_code=competition_code,
            offset=offset,
            limit=limit,
            matches_evaluated=(
                validation.matches_evaluated
            ),
            overall_accuracy=(
                validation.accuracy
            ),
            overall_brier_score=(
                validation.average_brier_score
            ),
            overall_log_loss=(
                validation.average_log_loss
            ),
            probability_segments=(
                probability_segments
            ),
            confidence_segments=(
                confidence_segments
            ),
            tournament_segments=(
                tournament_segments
            ),
            stage_segments=(
                stage_segments
            ),
        )

    @classmethod
    def _numeric_segment(
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
                lower
                <= float(
                    value_getter(record)
                )
                < upper
            )
        )

        upper_label = (
            "100"
            if upper == 101
            else str(upper)
        )

        return cls._summarise(
            selected,
            dimension=dimension,
            segment=(
                f"{lower}-{upper_label}"
            ),
        )

    @classmethod
    def _categorical_segments(
        cls,
        records,
        *,
        dimension,
        value_getter,
    ):
        grouped = {}

        for record in records:
            name = str(
                value_getter(record)
            )

            grouped.setdefault(
                name,
                [],
            ).append(record)

        return tuple(
            cls._summarise(
                tuple(selected),
                dimension=dimension,
                segment=name,
            )
            for name, selected
            in sorted(
                grouped.items(),
                key=lambda item: (
                    -len(item[1]),
                    item[0],
                ),
            )
        )

    @classmethod
    def _summarise(
        cls,
        records,
        *,
        dimension,
        segment,
    ):
        predictions = len(records)

        correct = sum(
            int(record.correct)
            for record in records
        )

        return V33PerformanceSegment(
            dimension=dimension,
            segment=segment,
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
                    record.brier_score
                    for record in records
                )
            ),
            average_log_loss=(
                cls._average(
                    record.log_loss
                    for record in records
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
