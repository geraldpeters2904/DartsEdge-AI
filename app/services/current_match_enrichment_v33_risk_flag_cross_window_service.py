from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from app.services.current_match_enrichment_v33_dual_low_history_risk_flag_service import (
    CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService,
)


@dataclass(frozen=True)
class V33RiskFlagCrossWindowResult:
    offset: int
    limit: int

    segment_matches: int
    flagged_matches: int
    filtered_matches: int

    coverage_retained: Optional[float]

    full_accuracy: Optional[float]
    flagged_accuracy: Optional[float]
    filtered_accuracy: Optional[float]

    accuracy_gain: Optional[float]

    full_brier: Optional[float]
    filtered_brier: Optional[float]
    brier_gain: Optional[float]

    full_log_loss: Optional[float]
    filtered_log_loss: Optional[float]
    log_loss_gain: Optional[float]


@dataclass(frozen=True)
class V33RiskFlagCrossWindowReport:
    model_version: str

    probability_lower: float
    probability_upper: float
    history_threshold: int
    agreement_threshold: float

    windows_completed: int
    windows_with_flags: int

    accuracy_improved_windows: int
    brier_improved_windows: int
    log_loss_improved_windows: int

    all_metrics_improved_windows: int

    total_segment_matches: int
    total_flagged_matches: int
    total_filtered_matches: int

    windows: Tuple[
        V33RiskFlagCrossWindowResult,
        ...
    ]


class CurrentMatchEnrichmentV33RiskFlagCrossWindowService:
    """
    Read-only cross-window validation for the sparse-consensus
    risk flag.

    Each historical window is evaluated independently.

    No model behaviour is modified.
    """

    def __init__(
        self,
        *,
        risk_flag_service=None,
    ) -> None:
        self.risk_flag_service = (
            risk_flag_service
            or CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService()
        )

    def analyse(
        self,
        db,
        *,
        offsets: Iterable[int],
        window_size: int = 2000,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        agreement_threshold: float = 100.0,
        competition_code: Optional[str] = "MODUS",
    ) -> V33RiskFlagCrossWindowReport:
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

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                limit=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                agreement_threshold=agreement_threshold,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33RiskFlagCrossWindowReport(
            model_version="transparent-v3.3",
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_threshold=history_threshold,
            agreement_threshold=agreement_threshold,
            windows_completed=len(windows),
            windows_with_flags=sum(
                1
                for item in windows
                if item.flagged_matches > 0
            ),
            accuracy_improved_windows=sum(
                1
                for item in windows
                if (
                    item.accuracy_gain is not None
                    and item.accuracy_gain > 0.0
                )
            ),
            brier_improved_windows=sum(
                1
                for item in windows
                if (
                    item.brier_gain is not None
                    and item.brier_gain > 0.0
                )
            ),
            log_loss_improved_windows=sum(
                1
                for item in windows
                if (
                    item.log_loss_gain is not None
                    and item.log_loss_gain > 0.0
                )
            ),
            all_metrics_improved_windows=sum(
                1
                for item in windows
                if (
                    item.accuracy_gain is not None
                    and item.brier_gain is not None
                    and item.log_loss_gain is not None
                    and item.accuracy_gain > 0.0
                    and item.brier_gain > 0.0
                    and item.log_loss_gain > 0.0
                )
            ),
            total_segment_matches=sum(
                item.segment_matches
                for item in windows
            ),
            total_flagged_matches=sum(
                item.flagged_matches
                for item in windows
            ),
            total_filtered_matches=sum(
                item.filtered_matches
                for item in windows
            ),
            windows=windows,
        )

    def _analyse_window(
        self,
        db,
        *,
        offset,
        limit,
        probability_lower,
        probability_upper,
        history_threshold,
        agreement_threshold,
        competition_code,
    ):
        report = (
            self.risk_flag_service
            .analyse(
                db,
                offset=offset,
                limit=limit,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                agreement_threshold=agreement_threshold,
                competition_code=competition_code,
            )
        )

        full = report.full_segment
        flagged = report.flagged
        filtered = report.filtered

        return V33RiskFlagCrossWindowResult(
            offset=offset,
            limit=limit,
            segment_matches=(
                report.segment_matches
            ),
            flagged_matches=(
                report.flagged_matches
            ),
            filtered_matches=(
                report.filtered_matches
            ),
            coverage_retained=(
                report.coverage_retained
            ),
            full_accuracy=(
                full.accuracy
            ),
            flagged_accuracy=(
                flagged.accuracy
            ),
            filtered_accuracy=(
                filtered.accuracy
            ),
            accuracy_gain=self._gain(
                full.accuracy,
                filtered.accuracy,
            ),
            full_brier=(
                full.brier_score
            ),
            filtered_brier=(
                filtered.brier_score
            ),
            brier_gain=self._loss_gain(
                full.brier_score,
                filtered.brier_score,
            ),
            full_log_loss=(
                full.log_loss
            ),
            filtered_log_loss=(
                filtered.log_loss
            ),
            log_loss_gain=self._loss_gain(
                full.log_loss,
                filtered.log_loss,
            ),
        )

    @staticmethod
    def _gain(
        baseline,
        filtered,
    ):
        if (
            baseline is None
            or filtered is None
        ):
            return None

        return round(
            float(filtered)
            - float(baseline),
            6,
        )

    @staticmethod
    def _loss_gain(
        baseline,
        filtered,
    ):
        if (
            baseline is None
            or filtered is None
        ):
            return None

        return round(
            float(baseline)
            - float(filtered),
            6,
        )
