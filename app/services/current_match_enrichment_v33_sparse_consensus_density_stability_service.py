from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from app.services.current_match_enrichment_v33_sparse_consensus_density_service import (
    CurrentMatchEnrichmentV33SparseConsensusDensityService,
)


@dataclass(frozen=True)
class V33SparseConsensusDensityScaleBand:
    window_size: int
    band: str

    windows: int
    flagged_matches: int
    average_flagged_accuracy: Optional[float]

    all_metrics_improved_windows: int

    average_accuracy_gain: Optional[float]
    average_brier_gain: Optional[float]
    average_log_loss_gain: Optional[float]

    positive_all_metrics: bool


@dataclass(frozen=True)
class V33SparseConsensusDensityStabilityBand:
    band: str

    scales_completed: int
    positive_scales: int
    stable_positive: bool

    scales: Tuple[
        V33SparseConsensusDensityScaleBand,
        ...
    ]


@dataclass(frozen=True)
class V33SparseConsensusDensityStabilityReport:
    model_version: str

    probability_lower: float
    probability_upper: float
    history_threshold: int
    agreement_threshold: float

    window_sizes: Tuple[int, ...]

    bands: Tuple[
        V33SparseConsensusDensityStabilityBand,
        ...
    ]

    above_one_percent_stable: bool


class CurrentMatchEnrichmentV33SparseConsensusDensityStabilityService:
    """
    Read-only cross-scale stability diagnostic for sparse-consensus
    density risk.

    The service evaluates the same density bands across multiple
    historical window sizes.

    A scale is considered positive for a band when average accuracy,
    Brier and log-loss gains are all greater than zero.

    No model behaviour is modified.
    """

    TARGET_BANDS = (
        "gt0_to_1",
        "gt1_to_3",
        "gt3",
    )

    def __init__(
        self,
        *,
        density_service=None,
    ) -> None:
        self.density_service = (
            density_service
            or CurrentMatchEnrichmentV33SparseConsensusDensityService()
        )

    def analyse(
        self,
        db,
        *,
        window_sizes: Iterable[int],
        history_limit: int = 17000,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        agreement_threshold: float = 100.0,
        competition_code: Optional[str] = "MODUS",
    ) -> V33SparseConsensusDensityStabilityReport:
        window_sizes = tuple(
            int(value)
            for value in window_sizes
        )

        if not window_sizes:
            raise ValueError(
                "Enter at least one window size."
            )

        if any(
            value <= 0
            for value in window_sizes
        ):
            raise ValueError(
                "Window sizes must be greater than zero."
            )

        if history_limit <= 0:
            raise ValueError(
                "history_limit must be greater than zero."
            )

        scale_reports = []

        for window_size in window_sizes:
            offsets = tuple(
                range(
                    0,
                    history_limit,
                    window_size,
                )
            )

            report = (
                self.density_service
                .analyse(
                    db,
                    offsets=offsets,
                    window_size=window_size,
                    probability_lower=probability_lower,
                    probability_upper=probability_upper,
                    history_threshold=history_threshold,
                    agreement_threshold=agreement_threshold,
                    competition_code=competition_code,
                )
            )

            scale_reports.append(
                (
                    window_size,
                    report,
                )
            )

        bands = tuple(
            self._build_band(
                band,
                scale_reports,
            )
            for band in self.TARGET_BANDS
        )

        above_one = tuple(
            item
            for item in bands
            if item.band
            in {
                "gt1_to_3",
                "gt3",
            }
        )

        above_one_percent_stable = (
            bool(above_one)
            and all(
                item.stable_positive
                for item in above_one
                if any(
                    scale.windows > 0
                    for scale in item.scales
                )
            )
        )

        return (
            V33SparseConsensusDensityStabilityReport(
                model_version="transparent-v3.3",
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                agreement_threshold=agreement_threshold,
                window_sizes=window_sizes,
                bands=bands,
                above_one_percent_stable=(
                    above_one_percent_stable
                ),
            )
        )

    def _build_band(
        self,
        band,
        scale_reports,
    ):
        scales = tuple(
            self._scale_band(
                window_size,
                self._find_band(
                    report,
                    band,
                ),
            )
            for window_size, report
            in scale_reports
        )

        positive_scales = sum(
            1
            for item in scales
            if item.positive_all_metrics
        )

        active_scales = tuple(
            item
            for item in scales
            if item.windows > 0
        )

        stable_positive = (
            bool(active_scales)
            and all(
                item.positive_all_metrics
                for item in active_scales
            )
        )

        return (
            V33SparseConsensusDensityStabilityBand(
                band=band,
                scales_completed=len(scales),
                positive_scales=positive_scales,
                stable_positive=stable_positive,
                scales=scales,
            )
        )

    @staticmethod
    def _find_band(
        report,
        band,
    ):
        return next(
            (
                item
                for item in report.bands
                if item.band == band
            ),
            None,
        )

    @staticmethod
    def _scale_band(
        window_size,
        band,
    ):
        if band is None:
            return (
                V33SparseConsensusDensityScaleBand(
                    window_size=window_size,
                    band="unknown",
                    windows=0,
                    flagged_matches=0,
                    average_flagged_accuracy=None,
                    all_metrics_improved_windows=0,
                    average_accuracy_gain=None,
                    average_brier_gain=None,
                    average_log_loss_gain=None,
                    positive_all_metrics=False,
                )
            )

        positive = (
            band.average_accuracy_gain is not None
            and band.average_brier_gain is not None
            and band.average_log_loss_gain is not None
            and band.average_accuracy_gain > 0.0
            and band.average_brier_gain > 0.0
            and band.average_log_loss_gain > 0.0
        )

        return (
            V33SparseConsensusDensityScaleBand(
                window_size=window_size,
                band=band.band,
                windows=band.windows,
                flagged_matches=band.flagged_matches,
                average_flagged_accuracy=(
                    band.average_flagged_accuracy
                ),
                all_metrics_improved_windows=(
                    band.all_metrics_improved_windows
                ),
                average_accuracy_gain=(
                    band.average_accuracy_gain
                ),
                average_brier_gain=(
                    band.average_brier_gain
                ),
                average_log_loss_gain=(
                    band.average_log_loss_gain
                ),
                positive_all_metrics=positive,
            )
        )
