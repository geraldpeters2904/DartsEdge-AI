from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
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
class CurrentMatchEnrichmentV33ValidationResult:
    model_version: str
    competition_code: Optional[str]

    offset: int
    limit: int

    match_ids: Tuple[int, ...]

    matches_considered: int
    matches_evaluated: int
    matches_skipped: int

    correct_predictions: int
    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]


class CurrentMatchEnrichmentV33ValidationService:
    """
    Read-only historical validation of the active transparent-v3.3
    prediction model.

    Completed matches are selected deterministically and evaluated
    through the existing no-look-ahead historical snapshot path.

    This service does not modify model weights or warehouse data.
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

    def validate(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 100,
        competition_code: Optional[str] = "MODUS",
    ) -> CurrentMatchEnrichmentV33ValidationResult:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        match_ids = self._select_match_ids(
            db,
            offset=offset,
            limit=limit,
        )

        validator = PredictionValidationEngine(
            snapshot_engine=self.snapshot_engine,
            prediction_engine=self.prediction_engine,
        )

        report = validator.validate_matches(
            db,
            match_ids=match_ids,
            competition_code=competition_code,
            include_records=False,
        )

        return CurrentMatchEnrichmentV33ValidationResult(
            model_version=report.model_version,
            competition_code=competition_code,
            offset=offset,
            limit=limit,
            match_ids=tuple(match_ids),
            matches_considered=report.matches_considered,
            matches_evaluated=report.matches_evaluated,
            matches_skipped=report.matches_skipped,
            correct_predictions=report.correct_predictions,
            accuracy=report.accuracy,
            average_brier_score=report.average_brier_score,
            average_log_loss=report.average_log_loss,
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
