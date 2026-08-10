from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_segment_stability_service import (
    CurrentMatchEnrichmentV33SegmentStabilityService,
    V33SegmentStabilityReport,
)


@dataclass(frozen=True)
class V33LowHistoryCalibrationComparison:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float

    low_history_upper: int
    control_history_lower: int
    control_history_upper: int

    low_history: V33SegmentStabilityReport
    control: V33SegmentStabilityReport

    accuracy_gap: Optional[float]
    brier_gap: Optional[float]
    log_loss_gap: Optional[float]

    low_history_weaker_accuracy: bool
    low_history_weaker_brier: bool
    low_history_weaker_log_loss: bool

    weakness_confirmed: bool


class CurrentMatchEnrichmentV33LowHistoryCalibrationService:
    """
    Compare low-history and established-history calibration for
    the same transparent-v3.3 favourite-probability band.

    The historical evaluation is delegated to the existing
    cross-window segment stability service.
    """

    def __init__(
        self,
        *,
        stability_service=None,
    ) -> None:
        self.stability_service = (
            stability_service
            or CurrentMatchEnrichmentV33SegmentStabilityService()
        )

    def analyse(
        self,
        db: Session,
        *,
        offsets: Iterable[int],
        window_size: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        low_history_upper: int = 10,
        control_history_lower: int = 10,
        control_history_upper: int = 20,
        competition_code: Optional[str] = "MODUS",
    ) -> V33LowHistoryCalibrationComparison:
        selected_offsets = tuple(
            int(value)
            for value in offsets
        )

        if not selected_offsets:
            raise ValueError(
                "Enter at least one window offset."
            )

        if low_history_upper <= 0:
            raise ValueError(
                "low_history_upper must be greater than zero."
            )

        if control_history_lower < low_history_upper:
            raise ValueError(
                "control_history_lower cannot overlap "
                "the low-history range."
            )

        if control_history_upper <= control_history_lower:
            raise ValueError(
                "control_history_upper must exceed "
                "control_history_lower."
            )

        low_history = (
            self.stability_service.analyse(
                db,
                offsets=selected_offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_lower=0,
                history_upper=low_history_upper,
                competition_code=competition_code,
            )
        )

        control = (
            self.stability_service.analyse(
                db,
                offsets=selected_offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_lower=control_history_lower,
                history_upper=control_history_upper,
                competition_code=competition_code,
            )
        )

        accuracy_gap = self._difference(
            low_history.weighted_accuracy,
            control.weighted_accuracy,
        )

        brier_gap = self._difference(
            low_history.weighted_brier_score,
            control.weighted_brier_score,
        )

        log_loss_gap = self._difference(
            low_history.weighted_log_loss,
            control.weighted_log_loss,
        )

        weaker_accuracy = (
            accuracy_gap is not None
            and accuracy_gap < 0
        )

        weaker_brier = (
            brier_gap is not None
            and brier_gap > 0
        )

        weaker_log_loss = (
            log_loss_gap is not None
            and log_loss_gap > 0
        )

        weakness_confirmed = (
            weaker_accuracy
            and weaker_brier
            and weaker_log_loss
            and low_history.total_segment_matches >= 50
            and control.total_segment_matches >= 50
        )

        return V33LowHistoryCalibrationComparison(
            model_version=(
                low_history.model_version
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            low_history_upper=low_history_upper,
            control_history_lower=control_history_lower,
            control_history_upper=control_history_upper,
            low_history=low_history,
            control=control,
            accuracy_gap=accuracy_gap,
            brier_gap=brier_gap,
            log_loss_gap=log_loss_gap,
            low_history_weaker_accuracy=(
                weaker_accuracy
            ),
            low_history_weaker_brier=(
                weaker_brier
            ),
            low_history_weaker_log_loss=(
                weaker_log_loss
            ),
            weakness_confirmed=(
                weakness_confirmed
            ),
        )

    @staticmethod
    def _difference(
        left,
        right,
    ):
        if left is None or right is None:
            return None

        return round(
            float(left) - float(right),
            6,
        )
