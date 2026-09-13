from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)
from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)
from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
)


@dataclass(frozen=True)
class ModelSegmentMetric:
    segment_type: str
    segment_label: str
    predictions: int
    correct: int
    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]


@dataclass(frozen=True)
class ModelSegmentSummary:
    model_name: str
    model_version: str
    matches_evaluated: int
    favourite_bands: Tuple[ModelSegmentMetric, ...]
    confidence_bands: Tuple[ModelSegmentMetric, ...]
    stages: Tuple[ModelSegmentMetric, ...]


@dataclass(frozen=True)
class ModelSegmentComparison:
    matches_requested: int
    matches_selected: int
    model_summaries: Tuple[ModelSegmentSummary, ...]


class ModelSegmentLaboratory:
    """
    Compare models by favourite strength, confidence and match stage.

    Each model receives the same selected historical match IDs. Historical
    snapshot routing preserves the no-look-ahead rules for both v1 and v2.
    """

    FAVOURITE_BANDS = (
        ("50-60", 50.0, 60.0),
        ("60-70", 60.0, 70.0),
        ("70-80", 70.0, 80.0),
        ("80+", 80.0, 101.0),
    )

    CONFIDENCE_BANDS = (
        ("0-40", 0.0, 40.0),
        ("40-60", 40.0, 60.0),
        ("60-80", 60.0, 80.0),
        ("80+", 80.0, 101.0),
    )

    def __init__(
        self,
        *,
        model_registry: Optional[
            PredictionModelRegistry
        ] = None,
    ) -> None:
        self.model_registry = (
            model_registry
            or prediction_model_registry
        )

    def compare(
        self,
        db: Session,
        *,
        model_names: Optional[Iterable[str]] = None,
        offset: int = 0,
        limit: int = 500,
        competition_code: Optional[str] = None,
    ) -> ModelSegmentComparison:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )
        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        selected_models = tuple(
            model_names
            if model_names is not None
            else self.model_registry.names()
        )

        match_ids = self._select_match_ids(
            db,
            offset=offset,
            limit=limit,
        )

        summaries = tuple(
            self._evaluate_model(
                db,
                model_name=model_name,
                match_ids=match_ids,
                competition_code=competition_code,
            )
            for model_name in selected_models
        )

        return ModelSegmentComparison(
            matches_requested=limit,
            matches_selected=len(match_ids),
            model_summaries=summaries,
        )

    def _evaluate_model(
        self,
        db: Session,
        *,
        model_name: str,
        match_ids,
        competition_code: Optional[str],
    ) -> ModelSegmentSummary:
        registered = (
            self.model_registry
            .get_registered(model_name)
        )

        snapshot_engine = (
            AdvancedHistoricalSnapshotEngine()
            if registered.version in {
                    "transparent-v2",
                    "transparent-v3",
                    "transparent-v3.1",
                    "transparent-v3.2",
                    "transparent-v3.3",
                    "transparent-v3.4",
                    "transparent-v3.5",
                }
            else PredictionSnapshotEngine()
        )

        report = PredictionValidationEngine(
            snapshot_engine=snapshot_engine,
            prediction_engine=registered.model,
        ).validate_matches(
            db,
            match_ids=match_ids,
            competition_code=competition_code,
            include_records=True,
        )

        records = report.records

        return ModelSegmentSummary(
            model_name=registered.name,
            model_version=registered.version,
            matches_evaluated=report.matches_evaluated,
            favourite_bands=tuple(
                self._metric(
                    records,
                    segment_type="favourite",
                    segment_label=label,
                    predicate=lambda record, lo=lower, hi=upper: (
                        lo
                        <= record.favourite_probability
                        < hi
                    ),
                )
                for label, lower, upper
                in self.FAVOURITE_BANDS
            ),
            confidence_bands=tuple(
                self._metric(
                    records,
                    segment_type="confidence",
                    segment_label=label,
                    predicate=lambda record, lo=lower, hi=upper: (
                        lo <= record.confidence < hi
                    ),
                )
                for label, lower, upper
                in self.CONFIDENCE_BANDS
            ),
            stages=tuple(
                self._metric(
                    records,
                    segment_type="stage",
                    segment_label=stage,
                    predicate=lambda record, value=stage: (
                        (record.stage or "Unknown")
                        == value
                    ),
                )
                for stage in sorted({
                    record.stage or "Unknown"
                    for record in records
                })
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

    @classmethod
    def _metric(
        cls,
        records,
        *,
        segment_type: str,
        segment_label: str,
        predicate,
    ) -> ModelSegmentMetric:
        selected = [
            record
            for record in records
            if predicate(record)
        ]

        correct = sum(
            int(record.correct)
            for record in selected
        )

        return ModelSegmentMetric(
            segment_type=segment_type,
            segment_label=segment_label,
            predictions=len(selected),
            correct=correct,
            accuracy=(
                cls._percentage(
                    correct,
                    len(selected),
                )
                if selected
                else None
            ),
            average_brier_score=cls._average(
                record.brier_score
                for record in selected
            ),
            average_log_loss=cls._average(
                record.log_loss
                for record in selected
            ),
        )

    @staticmethod
    def _average(values) -> Optional[float]:
        available = [
            float(value)
            for value in values
        ]

        if not available:
            return None

        return round(
            sum(available) / len(available),
            6,
        )

    @staticmethod
    def _percentage(
        numerator: int,
        denominator: int,
    ) -> float:
        if denominator == 0:
            return 0.0

        return round(
            numerator / denominator * 100,
            3,
        )
