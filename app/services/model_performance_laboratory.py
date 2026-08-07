from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)
from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)
from app.services.prediction_validation_engine import (
    PredictionValidationEngine,
    PredictionValidationReport,
)


@dataclass(frozen=True)
class ModelPerformanceSummary:
    model_name: str
    model_version: str

    matches_considered: int
    matches_evaluated: int
    matches_skipped: int

    correct_predictions: int
    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]

    best_confidence_band: Optional[str]
    best_confidence_accuracy: Optional[float]

    weakest_confidence_band: Optional[str]
    weakest_confidence_accuracy: Optional[float]

    best_tournament: Optional[str]
    best_tournament_accuracy: Optional[float]

    weakest_tournament: Optional[str]
    weakest_tournament_accuracy: Optional[float]

    best_stage: Optional[str]
    best_stage_accuracy: Optional[float]

    weakest_stage: Optional[str]
    weakest_stage_accuracy: Optional[float]


@dataclass(frozen=True)
class ModelComparisonResult:
    models_tested: int
    best_model_name: Optional[str]
    best_model_version: Optional[str]

    best_accuracy: Optional[float]
    best_brier_score: Optional[float]
    best_log_loss: Optional[float]

    summaries: Tuple[ModelPerformanceSummary, ...]


class ModelPerformanceLaboratory:
    """
    Compare registered prediction models on the same historical matches.

    Models are evaluated through PredictionValidationEngine, ensuring every
    comparison uses the same pre-match snapshot rules and validation metrics.
    """

    def __init__(
        self,
        *,
        model_registry: Optional[
            PredictionModelRegistry
        ] = None,
        snapshot_engine: Optional[
            PredictionSnapshotEngine
        ] = None,
    ) -> None:
        self.model_registry = (
            model_registry
            or prediction_model_registry
        )
        self.snapshot_engine = (
            snapshot_engine
            or PredictionSnapshotEngine()
        )

    def evaluate_model(
        self,
        db: Session,
        *,
        model_name: Optional[str] = None,
        match_ids: Optional[Iterable[int]] = None,
        competition_code: Optional[str] = None,
    ) -> ModelPerformanceSummary:
        registered = (
            self.model_registry
            .get_registered(model_name)
        )

        snapshot_engine = self.snapshot_engine

        if registered.version in {
                    "transparent-v2",
                    "transparent-v3",
                    "transparent-v3.1",
                    "transparent-v3.2",
                    "transparent-v3.3",
                }:
            from app.services.advanced_historical_snapshot_engine import (
                AdvancedHistoricalSnapshotEngine,
            )

            snapshot_engine = (
                AdvancedHistoricalSnapshotEngine()
            )

        validation = PredictionValidationEngine(
            snapshot_engine=snapshot_engine,
            prediction_engine=registered.model,
        )

        report = validation.validate_matches(
            db,
            match_ids=match_ids,
            competition_code=competition_code,
            include_records=False,
        )

        return self._summarise(
            registered.name,
            registered.version,
            report,
        )

    def compare_models(
        self,
        db: Session,
        *,
        model_names: Optional[Iterable[str]] = None,
        match_ids: Optional[Iterable[int]] = None,
        competition_code: Optional[str] = None,
    ) -> ModelComparisonResult:
        selected_names = tuple(
            model_names
            if model_names is not None
            else self.model_registry.names()
        )

        if not selected_names:
            return ModelComparisonResult(
                models_tested=0,
                best_model_name=None,
                best_model_version=None,
                best_accuracy=None,
                best_brier_score=None,
                best_log_loss=None,
                summaries=(),
            )

        summaries = tuple(
            self.evaluate_model(
                db,
                model_name=name,
                match_ids=match_ids,
                competition_code=competition_code,
            )
            for name in selected_names
        )

        ranked = sorted(
            summaries,
            key=self._ranking_key,
        )

        best = ranked[0] if ranked else None

        return ModelComparisonResult(
            models_tested=len(summaries),
            best_model_name=(
                best.model_name
                if best is not None
                else None
            ),
            best_model_version=(
                best.model_version
                if best is not None
                else None
            ),
            best_accuracy=(
                best.accuracy
                if best is not None
                else None
            ),
            best_brier_score=(
                best.average_brier_score
                if best is not None
                else None
            ),
            best_log_loss=(
                best.average_log_loss
                if best is not None
                else None
            ),
            summaries=tuple(ranked),
        )

    @classmethod
    def _summarise(
        cls,
        model_name: str,
        model_version: str,
        report: PredictionValidationReport,
    ) -> ModelPerformanceSummary:
        (
            best_confidence_band,
            best_confidence_accuracy,
        ) = cls._best_confidence_band(report)

        (
            weakest_confidence_band,
            weakest_confidence_accuracy,
        ) = cls._weakest_confidence_band(
            report
        )

        (
            best_tournament,
            best_tournament_accuracy,
        ) = cls._best_mapping_value(
            report.accuracy_by_tournament
        )

        (
            weakest_tournament,
            weakest_tournament_accuracy,
        ) = cls._weakest_mapping_value(
            report.accuracy_by_tournament
        )

        (
            best_stage,
            best_stage_accuracy,
        ) = cls._best_mapping_value(
            report.accuracy_by_stage
        )

        (
            weakest_stage,
            weakest_stage_accuracy,
        ) = cls._weakest_mapping_value(
            report.accuracy_by_stage
        )

        return ModelPerformanceSummary(
            model_name=model_name,
            model_version=model_version,
            matches_considered=(
                report.matches_considered
            ),
            matches_evaluated=(
                report.matches_evaluated
            ),
            matches_skipped=(
                report.matches_skipped
            ),
            correct_predictions=(
                report.correct_predictions
            ),
            accuracy=report.accuracy,
            average_brier_score=(
                report.average_brier_score
            ),
            average_log_loss=(
                report.average_log_loss
            ),
            best_confidence_band=(
                best_confidence_band
            ),
            best_confidence_accuracy=(
                best_confidence_accuracy
            ),
            weakest_confidence_band=(
                weakest_confidence_band
            ),
            weakest_confidence_accuracy=(
                weakest_confidence_accuracy
            ),
            best_tournament=best_tournament,
            best_tournament_accuracy=(
                best_tournament_accuracy
            ),
            weakest_tournament=(
                weakest_tournament
            ),
            weakest_tournament_accuracy=(
                weakest_tournament_accuracy
            ),
            best_stage=best_stage,
            best_stage_accuracy=(
                best_stage_accuracy
            ),
            weakest_stage=weakest_stage,
            weakest_stage_accuracy=(
                weakest_stage_accuracy
            ),
        )

    @staticmethod
    def _best_confidence_band(
        report: PredictionValidationReport,
    ):
        available = [
            band
            for band in report.confidence_bands
            if (
                band.predictions > 0
                and band.accuracy is not None
            )
        ]

        if not available:
            return None, None

        best = max(
            available,
            key=lambda band: (
                band.accuracy,
                band.predictions,
            ),
        )

        return (
            f"{best.lower_bound}-{best.upper_bound}",
            best.accuracy,
        )

    @staticmethod
    def _weakest_confidence_band(
        report: PredictionValidationReport,
    ):
        available = [
            band
            for band in report.confidence_bands
            if (
                band.predictions > 0
                and band.accuracy is not None
            )
        ]

        if not available:
            return None, None

        weakest = min(
            available,
            key=lambda band: (
                band.accuracy,
                -band.predictions,
            ),
        )

        return (
            f"{weakest.lower_bound}-{weakest.upper_bound}",
            weakest.accuracy,
        )

    @staticmethod
    def _best_mapping_value(
        values: Dict[str, float],
    ):
        if not values:
            return None, None

        name, score = max(
            values.items(),
            key=lambda item: (
                item[1],
                item[0],
            ),
        )

        return name, score

    @staticmethod
    def _weakest_mapping_value(
        values: Dict[str, float],
    ):
        if not values:
            return None, None

        name, score = min(
            values.items(),
            key=lambda item: (
                item[1],
                item[0],
            ),
        )

        return name, score

    @staticmethod
    def _ranking_key(
        summary: ModelPerformanceSummary,
    ):
        accuracy = (
            summary.accuracy
            if summary.accuracy is not None
            else -1.0
        )
        brier = (
            summary.average_brier_score
            if summary.average_brier_score
            is not None
            else float("inf")
        )
        log_loss = (
            summary.average_log_loss
            if summary.average_log_loss
            is not None
            else float("inf")
        )

        return (
            -accuracy,
            brier,
            log_loss,
            summary.model_name,
        )
