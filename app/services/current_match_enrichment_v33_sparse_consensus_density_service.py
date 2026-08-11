from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from app.services.current_match_enrichment_v33_risk_flag_cross_window_service import (
    CurrentMatchEnrichmentV33RiskFlagCrossWindowService,
)


@dataclass(frozen=True)
class V33SparseConsensusDensityWindow:
    offset: int
    segment_matches: int
    flagged_matches: int
    flagged_density: Optional[float]
    density_band: str

    flagged_accuracy: Optional[float]

    accuracy_gain: Optional[float]
    brier_gain: Optional[float]
    log_loss_gain: Optional[float]

    all_metrics_improved: bool


@dataclass(frozen=True)
class V33SparseConsensusDensityBand:
    band: str
    windows: int
    segment_matches: int
    flagged_matches: int

    average_density: Optional[float]
    average_flagged_accuracy: Optional[float]

    accuracy_improved_windows: int
    brier_improved_windows: int
    log_loss_improved_windows: int
    all_metrics_improved_windows: int

    average_accuracy_gain: Optional[float]
    average_brier_gain: Optional[float]
    average_log_loss_gain: Optional[float]


@dataclass(frozen=True)
class V33SparseConsensusDensityReport:
    model_version: str
    probability_lower: float
    probability_upper: float
    history_threshold: int
    agreement_threshold: float

    windows_completed: int
    windows_with_flags: int

    windows: Tuple[
        V33SparseConsensusDensityWindow,
        ...
    ]

    bands: Tuple[
        V33SparseConsensusDensityBand,
        ...
    ]


class CurrentMatchEnrichmentV33SparseConsensusDensityService:
    """
    Read-only diagnostic measuring whether sparse-consensus
    risk becomes more reliable when flagged predictions
    cluster within a historical window.

    Density is:

        flagged predictions / segment predictions * 100

    Bands:
        zero       = 0%
        gt0_to_1   = >0% to 1%
        gt1_to_3   = >1% to 3%
        gt3        = >3%
    """

    BAND_ORDER = (
        "zero",
        "gt0_to_1",
        "gt1_to_3",
        "gt3",
    )

    def __init__(
        self,
        *,
        cross_window_service=None,
    ) -> None:
        self.cross_window_service = (
            cross_window_service
            or CurrentMatchEnrichmentV33RiskFlagCrossWindowService()
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
    ) -> V33SparseConsensusDensityReport:
        cross_report = (
            self.cross_window_service
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

        windows = tuple(
            self._window(item)
            for item in cross_report.windows
        )

        bands = tuple(
            self._aggregate_band(
                band,
                windows,
            )
            for band in self.BAND_ORDER
        )

        return V33SparseConsensusDensityReport(
            model_version=cross_report.model_version,
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
            windows=windows,
            bands=bands,
        )

    def _window(
        self,
        item,
    ) -> V33SparseConsensusDensityWindow:
        density = self._density(
            item.flagged_matches,
            item.segment_matches,
        )

        return V33SparseConsensusDensityWindow(
            offset=item.offset,
            segment_matches=item.segment_matches,
            flagged_matches=item.flagged_matches,
            flagged_density=density,
            density_band=self._density_band(
                density,
            ),
            flagged_accuracy=item.flagged_accuracy,
            accuracy_gain=item.accuracy_gain,
            brier_gain=item.brier_gain,
            log_loss_gain=item.log_loss_gain,
            all_metrics_improved=(
                item.accuracy_gain is not None
                and item.brier_gain is not None
                and item.log_loss_gain is not None
                and item.accuracy_gain > 0.0
                and item.brier_gain > 0.0
                and item.log_loss_gain > 0.0
            ),
        )

    @staticmethod
    def _density(
        flagged_matches,
        segment_matches,
    ) -> Optional[float]:
        if segment_matches <= 0:
            return None

        return round(
            flagged_matches
            / segment_matches
            * 100.0,
            6,
        )

    @staticmethod
    def _density_band(
        density,
    ) -> str:
        if density is None:
            return "zero"

        if density <= 0.0:
            return "zero"

        if density <= 1.0:
            return "gt0_to_1"

        if density <= 3.0:
            return "gt1_to_3"

        return "gt3"

    def _aggregate_band(
        self,
        band,
        windows,
    ) -> V33SparseConsensusDensityBand:
        selected = tuple(
            item
            for item in windows
            if item.density_band == band
        )

        densities = tuple(
            item.flagged_density
            for item in selected
            if item.flagged_density is not None
        )

        flagged_accuracy_pairs = tuple(
            (
                item.flagged_accuracy,
                item.flagged_matches,
            )
            for item in selected
            if (
                item.flagged_accuracy is not None
                and item.flagged_matches > 0
            )
        )

        accuracy_gains = tuple(
            item.accuracy_gain
            for item in selected
            if item.accuracy_gain is not None
        )

        brier_gains = tuple(
            item.brier_gain
            for item in selected
            if item.brier_gain is not None
        )

        log_loss_gains = tuple(
            item.log_loss_gain
            for item in selected
            if item.log_loss_gain is not None
        )

        total_flagged = sum(
            count
            for _, count
            in flagged_accuracy_pairs
        )

        average_flagged_accuracy = (
            round(
                sum(
                    accuracy * count
                    for accuracy, count
                    in flagged_accuracy_pairs
                )
                / total_flagged,
                6,
            )
            if total_flagged
            else None
        )

        return V33SparseConsensusDensityBand(
            band=band,
            windows=len(selected),
            segment_matches=sum(
                item.segment_matches
                for item in selected
            ),
            flagged_matches=sum(
                item.flagged_matches
                for item in selected
            ),
            average_density=self._average(
                densities,
            ),
            average_flagged_accuracy=(
                average_flagged_accuracy
            ),
            accuracy_improved_windows=sum(
                1
                for item in selected
                if (
                    item.accuracy_gain is not None
                    and item.accuracy_gain > 0.0
                )
            ),
            brier_improved_windows=sum(
                1
                for item in selected
                if (
                    item.brier_gain is not None
                    and item.brier_gain > 0.0
                )
            ),
            log_loss_improved_windows=sum(
                1
                for item in selected
                if (
                    item.log_loss_gain is not None
                    and item.log_loss_gain > 0.0
                )
            ),
            all_metrics_improved_windows=sum(
                1
                for item in selected
                if item.all_metrics_improved
            ),
            average_accuracy_gain=self._average(
                accuracy_gains,
            ),
            average_brier_gain=self._average(
                brier_gains,
            ),
            average_log_loss_gain=self._average(
                log_loss_gains,
            ),
        )

    @staticmethod
    def _average(
        values,
    ) -> Optional[float]:
        values = tuple(values)

        if not values:
            return None

        return round(
            sum(values) / len(values),
            6,
        )
