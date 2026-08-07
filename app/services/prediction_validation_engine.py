from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)
from app.services.transparent_prediction_engine import (
    MatchWinPrediction,
    TransparentPredictionEngine,
)


@dataclass(frozen=True)
class PredictionValidationRecord:
    match_id: int
    match_date: Optional[str]
    tournament: Optional[str]
    stage: Optional[str]

    player_a_name: str
    player_b_name: str
    actual_winner: str
    predicted_winner: str

    player_a_probability: float
    player_b_probability: float
    favourite_probability: float
    confidence: float

    correct: bool
    brier_score: float
    log_loss: float
    model_version: str


@dataclass(frozen=True)
class CalibrationBucket:
    lower_bound: int
    upper_bound: int
    predictions: int
    average_predicted_probability: Optional[float]
    observed_win_rate: Optional[float]


@dataclass(frozen=True)
class ConfidenceBand:
    lower_bound: int
    upper_bound: int
    predictions: int
    correct: int
    accuracy: Optional[float]


@dataclass(frozen=True)
class PredictionValidationReport:
    model_version: str
    matches_considered: int
    matches_evaluated: int
    matches_skipped: int

    correct_predictions: int
    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]

    calibration: Tuple[CalibrationBucket, ...]
    confidence_bands: Tuple[ConfidenceBand, ...]

    accuracy_by_tournament: Dict[str, float]
    accuracy_by_stage: Dict[str, float]

    records: Tuple[PredictionValidationRecord, ...]


class PredictionValidationEngine:
    """
    Back-test a prediction model against completed historical matches.

    This service is read-only. Each match is evaluated using a pre-match
    snapshot, so the target result and all later performances are excluded
    from the model inputs.
    """

    CALIBRATION_BUCKETS = (
        (50, 60),
        (60, 70),
        (70, 80),
        (80, 90),
        (90, 101),
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
        snapshot_engine: Optional[
            PredictionSnapshotEngine
        ] = None,
        prediction_engine: Optional[
            TransparentPredictionEngine
        ] = None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine
            or PredictionSnapshotEngine()
        )
        self.prediction_engine = (
            prediction_engine
            or TransparentPredictionEngine()
        )

    def validate_matches(
        self,
        db: Session,
        *,
        match_ids: Optional[Iterable[int]] = None,
        competition_code: Optional[str] = None,
        include_records: bool = True,
    ) -> PredictionValidationReport:
        query = db.query(Match).filter(
            Match.status == "completed"
        )

        if match_ids is not None:
            selected_ids = tuple(
                int(match_id)
                for match_id in match_ids
            )
            if not selected_ids:
                return self._empty_report()
            query = query.filter(
                Match.id.in_(selected_ids)
            )

        matches = query.order_by(
            Match.date.asc(),
            Match.id.asc(),
        ).all()

        records: List[
            PredictionValidationRecord
        ] = []
        skipped = 0

        for match in matches:
            if not self._has_valid_result(match):
                skipped += 1
                continue

            try:
                snapshot = (
                    self.snapshot_engine
                    .build_match_snapshot(
                        db,
                        match.id,
                        competition_code=(
                            competition_code
                        ),
                    )
                )
                prediction = (
                    self.prediction_engine
                    .predict(snapshot)
                )
            except Exception:
                skipped += 1
                continue

            records.append(
                self._build_record(
                    match=match,
                    prediction=prediction,
                )
            )

        report_records = (
            tuple(records)
            if include_records
            else ()
        )

        return PredictionValidationReport(
            model_version=(
                self.prediction_engine
                .MODEL_VERSION
            ),
            matches_considered=len(matches),
            matches_evaluated=len(records),
            matches_skipped=skipped,
            correct_predictions=sum(
                int(record.correct)
                for record in records
            ),
            accuracy=self._accuracy(records),
            average_brier_score=self._average(
                record.brier_score
                for record in records
            ),
            average_log_loss=self._average(
                record.log_loss
                for record in records
            ),
            calibration=self._calibration(records),
            confidence_bands=(
                self._confidence_bands(records)
            ),
            accuracy_by_tournament=(
                self._group_accuracy(
                    records,
                    key=lambda record: (
                        record.tournament
                        or "Unknown"
                    ),
                )
            ),
            accuracy_by_stage=(
                self._group_accuracy(
                    records,
                    key=lambda record: (
                        record.stage
                        or "Unknown"
                    ),
                )
            ),
            records=report_records,
        )

    def validate_one(
        self,
        db: Session,
        match_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> PredictionValidationRecord:
        report = self.validate_matches(
            db,
            match_ids=(match_id,),
            competition_code=competition_code,
            include_records=True,
        )

        if not report.records:
            raise ValueError(
                f"Match {match_id} could not be evaluated."
            )

        return report.records[0]

    def _build_record(
        self,
        *,
        match: Match,
        prediction: MatchWinPrediction,
    ) -> PredictionValidationRecord:
        actual_is_a = (
            match.winner
            == prediction.player_a_name
        )
        player_a_probability = (
            prediction.player_a_probability
            / 100.0
        )

        actual_value = (
            1.0
            if actual_is_a
            else 0.0
        )

        brier_score = (
            player_a_probability
            - actual_value
        ) ** 2

        actual_probability = (
            player_a_probability
            if actual_is_a
            else 1.0
            - player_a_probability
        )

        log_loss = self._log_loss(
            actual_probability
        )

        return PredictionValidationRecord(
            match_id=match.id,
            match_date=(
                match.date.isoformat()
                if match.date is not None
                else None
            ),
            tournament=match.tournament,
            stage=match.stage,
            player_a_name=(
                prediction.player_a_name
            ),
            player_b_name=(
                prediction.player_b_name
            ),
            actual_winner=match.winner,
            predicted_winner=(
                prediction.predicted_winner
            ),
            player_a_probability=(
                prediction.player_a_probability
            ),
            player_b_probability=(
                prediction.player_b_probability
            ),
            favourite_probability=max(
                prediction.player_a_probability,
                prediction.player_b_probability,
            ),
            confidence=prediction.confidence,
            correct=(
                prediction.predicted_winner
                == match.winner
            ),
            brier_score=round(
                brier_score,
                6,
            ),
            log_loss=round(
                log_loss,
                6,
            ),
            model_version=(
                prediction.model_version
            ),
        )

    @classmethod
    def _calibration(
        cls,
        records: List[
            PredictionValidationRecord
        ],
    ) -> Tuple[CalibrationBucket, ...]:
        buckets = []

        for lower, upper in (
            cls.CALIBRATION_BUCKETS
        ):
            selected = [
                record
                for record in records
                if (
                    lower
                    <= record.favourite_probability
                    < upper
                )
            ]

            buckets.append(
                CalibrationBucket(
                    lower_bound=lower,
                    upper_bound=upper,
                    predictions=len(selected),
                    average_predicted_probability=(
                        cls._average(
                            record.favourite_probability
                            for record in selected
                        )
                    ),
                    observed_win_rate=(
                        cls._percentage(
                            sum(
                                int(record.correct)
                                for record in selected
                            ),
                            len(selected),
                        )
                        if selected
                        else None
                    ),
                )
            )

        return tuple(buckets)

    @classmethod
    def _confidence_bands(
        cls,
        records: List[
            PredictionValidationRecord
        ],
    ) -> Tuple[ConfidenceBand, ...]:
        bands = []

        for lower, upper in (
            cls.CONFIDENCE_BANDS
        ):
            selected = [
                record
                for record in records
                if (
                    lower
                    <= record.confidence
                    < upper
                )
            ]
            correct = sum(
                int(record.correct)
                for record in selected
            )

            bands.append(
                ConfidenceBand(
                    lower_bound=lower,
                    upper_bound=upper,
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
                )
            )

        return tuple(bands)

    @classmethod
    def _group_accuracy(
        cls,
        records,
        *,
        key,
    ) -> Dict[str, float]:
        grouped: Dict[str, list] = {}

        for record in records:
            grouped.setdefault(
                str(key(record)),
                [],
            ).append(record)

        return {
            name: cls._percentage(
                sum(
                    int(record.correct)
                    for record in selected
                ),
                len(selected),
            )
            for name, selected in sorted(
                grouped.items()
            )
        }

    @staticmethod
    def _has_valid_result(
        match: Match,
    ) -> bool:
        players = {
            match.player_a,
            match.player_b,
        }

        return (
            len(players) == 2
            and bool(match.winner)
            and match.winner in players
        )

    @staticmethod
    def _log_loss(
        actual_probability: float,
    ) -> float:
        from math import log

        clipped = min(
            max(actual_probability, 1e-9),
            1.0 - 1e-9,
        )

        return -log(clipped)

    @classmethod
    def _accuracy(
        cls,
        records,
    ) -> Optional[float]:
        if not records:
            return None

        return cls._percentage(
            sum(
                int(record.correct)
                for record in records
            ),
            len(records),
        )

    @staticmethod
    def _average(
        values,
    ) -> Optional[float]:
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

    def _empty_report(
        self,
    ) -> PredictionValidationReport:
        return PredictionValidationReport(
            model_version=(
                self.prediction_engine
                .MODEL_VERSION
            ),
            matches_considered=0,
            matches_evaluated=0,
            matches_skipped=0,
            correct_predictions=0,
            accuracy=None,
            average_brier_score=None,
            average_log_loss=None,
            calibration=tuple(
                CalibrationBucket(
                    lower_bound=lower,
                    upper_bound=upper,
                    predictions=0,
                    average_predicted_probability=(
                        None
                    ),
                    observed_win_rate=None,
                )
                for lower, upper in (
                    self.CALIBRATION_BUCKETS
                )
            ),
            confidence_bands=tuple(
                ConfidenceBand(
                    lower_bound=lower,
                    upper_bound=upper,
                    predictions=0,
                    correct=0,
                    accuracy=None,
                )
                for lower, upper in (
                    self.CONFIDENCE_BANDS
                )
            ),
            accuracy_by_tournament={},
            accuracy_by_stage={},
            records=(),
        )
