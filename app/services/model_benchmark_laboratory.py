from __future__ import annotations

from dataclasses import dataclass
from statistics import median, pstdev
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.model_performance_laboratory import (
    ModelPerformanceLaboratory,
    ModelPerformanceSummary,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)


@dataclass(frozen=True)
class BenchmarkWindowResult:
    index: int
    offset: int
    requested_matches: int
    actual_matches: int
    summaries: Tuple[ModelPerformanceSummary, ...]
    accuracy_winner: Optional[str]
    brier_winner: Optional[str]
    log_loss_winner: Optional[str]


@dataclass(frozen=True)
class BenchmarkModelSummary:
    model_name: str
    model_version: str
    windows_evaluated: int
    matches_evaluated: int

    average_accuracy: Optional[float]
    median_accuracy: Optional[float]
    accuracy_standard_deviation: Optional[float]
    best_accuracy: Optional[float]
    worst_accuracy: Optional[float]
    accuracy_window_wins: int

    average_brier_score: Optional[float]
    best_brier_score: Optional[float]
    brier_window_wins: int

    average_log_loss: Optional[float]
    best_log_loss: Optional[float]
    log_loss_window_wins: int


@dataclass(frozen=True)
class BenchmarkReport:
    window_size: int
    windows_requested: int
    windows_completed: int
    starting_offset: int
    step_size: int
    total_unique_matches_requested: int

    best_accuracy_model: Optional[str]
    best_brier_model: Optional[str]
    best_log_loss_model: Optional[str]

    model_summaries: Tuple[BenchmarkModelSummary, ...]
    windows: Tuple[BenchmarkWindowResult, ...]


class ModelBenchmarkLaboratory:
    """
    Compare registered models across repeated equal-sized historical windows.

    Every model receives the same match IDs within each window. The service is
    read-only and reuses the existing model performance laboratory.
    """

    def __init__(
        self,
        *,
        performance_laboratory: Optional[
            ModelPerformanceLaboratory
        ] = None,
        model_registry: Optional[
            PredictionModelRegistry
        ] = None,
    ) -> None:
        self.performance_laboratory = (
            performance_laboratory
            or ModelPerformanceLaboratory()
        )
        self.model_registry = (
            model_registry
            or prediction_model_registry
        )

    def benchmark(
        self,
        db: Session,
        *,
        model_names: Optional[Iterable[str]] = None,
        start_offset: int = 0,
        window_size: int = 200,
        windows: int = 10,
        step_size: Optional[int] = None,
        competition_code: Optional[str] = None,
    ) -> BenchmarkReport:
        if start_offset < 0:
            raise ValueError(
                "start_offset cannot be negative."
            )
        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero."
            )
        if windows <= 0:
            raise ValueError(
                "windows must be greater than zero."
            )

        selected_models = tuple(
            model_names
            if model_names is not None
            else self.model_registry.names()
        )

        if not selected_models:
            raise ValueError(
                "At least one prediction model is required."
            )

        actual_step = (
            window_size
            if step_size is None
            else int(step_size)
        )

        if actual_step <= 0:
            raise ValueError(
                "step_size must be greater than zero."
            )

        window_results = []

        for index in range(windows):
            offset = (
                start_offset
                + index * actual_step
            )

            match_ids = self._select_match_ids(
                db,
                offset=offset,
                limit=window_size,
            )

            if not match_ids:
                break

            summaries = tuple(
                self.performance_laboratory
                .evaluate_model(
                    db,
                    model_name=model_name,
                    match_ids=match_ids,
                    competition_code=competition_code,
                )
                for model_name in selected_models
            )

            window_results.append(
                BenchmarkWindowResult(
                    index=index + 1,
                    offset=offset,
                    requested_matches=window_size,
                    actual_matches=len(match_ids),
                    summaries=summaries,
                    accuracy_winner=self._best_accuracy(
                        summaries
                    ),
                    brier_winner=self._best_brier(
                        summaries
                    ),
                    log_loss_winner=self._best_log_loss(
                        summaries
                    ),
                )
            )

        model_summaries = tuple(
            self._summarise_model(
                model_name,
                window_results,
            )
            for model_name in selected_models
        )

        return BenchmarkReport(
            window_size=window_size,
            windows_requested=windows,
            windows_completed=len(window_results),
            starting_offset=start_offset,
            step_size=actual_step,
            total_unique_matches_requested=(
                window_size
                + max(0, len(window_results) - 1)
                * actual_step
            )
            if window_results
            else 0,
            best_accuracy_model=(
                self._best_aggregate_accuracy(
                    model_summaries
                )
            ),
            best_brier_model=(
                self._best_aggregate_brier(
                    model_summaries
                )
            ),
            best_log_loss_model=(
                self._best_aggregate_log_loss(
                    model_summaries
                )
            ),
            model_summaries=model_summaries,
            windows=tuple(window_results),
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
    def _summarise_model(
        cls,
        model_name: str,
        windows,
    ) -> BenchmarkModelSummary:
        selected = []

        for window in windows:
            summary = next(
                (
                    item
                    for item in window.summaries
                    if item.model_name == model_name
                ),
                None,
            )

            if summary is not None:
                selected.append(summary)

        version = (
            selected[0].model_version
            if selected
            else ""
        )

        accuracies = [
            item.accuracy
            for item in selected
            if item.accuracy is not None
        ]
        briers = [
            item.average_brier_score
            for item in selected
            if item.average_brier_score is not None
        ]
        losses = [
            item.average_log_loss
            for item in selected
            if item.average_log_loss is not None
        ]

        return BenchmarkModelSummary(
            model_name=model_name,
            model_version=version,
            windows_evaluated=len(selected),
            matches_evaluated=sum(
                item.matches_evaluated
                for item in selected
            ),
            average_accuracy=cls._mean(
                accuracies
            ),
            median_accuracy=(
                round(median(accuracies), 6)
                if accuracies
                else None
            ),
            accuracy_standard_deviation=(
                round(pstdev(accuracies), 6)
                if len(accuracies) > 1
                else 0.0
                if accuracies
                else None
            ),
            best_accuracy=max(accuracies)
            if accuracies else None,
            worst_accuracy=min(accuracies)
            if accuracies else None,
            accuracy_window_wins=sum(
                int(
                    window.accuracy_winner
                    == model_name
                )
                for window in windows
            ),
            average_brier_score=cls._mean(
                briers
            ),
            best_brier_score=min(briers)
            if briers else None,
            brier_window_wins=sum(
                int(
                    window.brier_winner
                    == model_name
                )
                for window in windows
            ),
            average_log_loss=cls._mean(
                losses
            ),
            best_log_loss=min(losses)
            if losses else None,
            log_loss_window_wins=sum(
                int(
                    window.log_loss_winner
                    == model_name
                )
                for window in windows
            ),
        )

    @staticmethod
    def _best_accuracy(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.accuracy is not None
        ]
        if not available:
            return None

        return max(
            available,
            key=lambda item: (
                item.accuracy,
                -(
                    item.average_brier_score
                    if item.average_brier_score
                    is not None
                    else float("inf")
                ),
            ),
        ).model_name

    @staticmethod
    def _best_brier(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.average_brier_score
            is not None
        ]
        if not available:
            return None

        return min(
            available,
            key=lambda item: (
                item.average_brier_score,
                -(
                    item.accuracy
                    if item.accuracy is not None
                    else -1.0
                ),
            ),
        ).model_name

    @staticmethod
    def _best_log_loss(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.average_log_loss
            is not None
        ]
        if not available:
            return None

        return min(
            available,
            key=lambda item: (
                item.average_log_loss,
                -(
                    item.accuracy
                    if item.accuracy is not None
                    else -1.0
                ),
            ),
        ).model_name

    @staticmethod
    def _best_aggregate_accuracy(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.average_accuracy is not None
        ]
        if not available:
            return None
        return max(
            available,
            key=lambda item: item.average_accuracy,
        ).model_name

    @staticmethod
    def _best_aggregate_brier(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.average_brier_score
            is not None
        ]
        if not available:
            return None
        return min(
            available,
            key=lambda item: item.average_brier_score,
        ).model_name

    @staticmethod
    def _best_aggregate_log_loss(
        summaries,
    ) -> Optional[str]:
        available = [
            item
            for item in summaries
            if item.average_log_loss
            is not None
        ]
        if not available:
            return None
        return min(
            available,
            key=lambda item: item.average_log_loss,
        ).model_name

    @staticmethod
    def _mean(values) -> Optional[float]:
        if not values:
            return None
        return round(
            sum(float(value) for value in values)
            / len(values),
            6,
        )
