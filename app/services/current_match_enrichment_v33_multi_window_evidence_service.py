from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_feature_ablation_service import (
    CurrentMatchEnrichmentV33FeatureAblationService,
)


@dataclass(frozen=True)
class V33FeatureWindowEvidence:
    offset: int
    limit: int
    matches_evaluated: int
    baseline_accuracy: Optional[float]
    baseline_brier_score: Optional[float]
    baseline_log_loss: Optional[float]


@dataclass(frozen=True)
class V33FeatureConsensus:
    feature_name: str
    feature_weight: float

    windows: int
    helpful_windows: int
    harmful_windows: int
    neutral_windows: int

    average_importance: float
    average_accuracy_drop: Optional[float]
    average_brier_increase: Optional[float]
    average_log_loss_increase: Optional[float]

    helpful_percentage: float
    harmful_percentage: float


@dataclass(frozen=True)
class V33MultiWindowEvidenceReport:
    model_version: str
    competition_code: Optional[str]

    window_size: int
    offsets: Tuple[int, ...]

    windows_completed: int
    total_matches_evaluated: int

    windows: Tuple[V33FeatureWindowEvidence, ...]
    features: Tuple[V33FeatureConsensus, ...]


class CurrentMatchEnrichmentV33MultiWindowEvidenceService:
    """
    Aggregate transparent-v3.3 feature-ablation evidence across
    independent historical windows.

    This service is read-only and does not modify model weights.
    """

    def __init__(
        self,
        *,
        ablation_service=None,
    ) -> None:
        self.ablation_service = (
            ablation_service
            or CurrentMatchEnrichmentV33FeatureAblationService()
        )

    def analyse(
        self,
        db: Session,
        *,
        offsets,
        window_size: int = 100,
        competition_code: Optional[str] = "MODUS",
    ) -> V33MultiWindowEvidenceReport:
        selected_offsets = tuple(
            int(value)
            for value in offsets
        )

        if not selected_offsets:
            raise ValueError(
                "Enter at least one historical offset."
            )

        if any(
            offset < 0
            for offset in selected_offsets
        ):
            raise ValueError(
                "Offsets cannot be negative."
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero."
            )

        reports = tuple(
            self.ablation_service.analyse(
                db,
                offset=offset,
                limit=window_size,
                competition_code=competition_code,
            )
            for offset in selected_offsets
        )

        if not reports:
            raise ValueError(
                "No historical windows were analysed."
            )

        by_feature = {}

        for report in reports:
            for item in report.features:
                by_feature.setdefault(
                    item.feature_name,
                    [],
                ).append(item)

        feature_consensus = []

        for feature_name, items in by_feature.items():
            helpful = sum(
                int(item.helpful)
                for item in items
            )
            harmful = sum(
                int(item.harmful)
                for item in items
            )
            neutral = (
                len(items)
                - helpful
                - harmful
            )

            feature_consensus.append(
                V33FeatureConsensus(
                    feature_name=feature_name,
                    feature_weight=float(
                        items[0].feature_weight
                    ),
                    windows=len(items),
                    helpful_windows=helpful,
                    harmful_windows=harmful,
                    neutral_windows=neutral,
                    average_importance=self._average(
                        item.importance_score
                        for item in items
                    )
                    or 0.0,
                    average_accuracy_drop=self._average(
                        item.accuracy_drop
                        for item in items
                    ),
                    average_brier_increase=self._average(
                        item.brier_increase
                        for item in items
                    ),
                    average_log_loss_increase=self._average(
                        item.log_loss_increase
                        for item in items
                    ),
                    helpful_percentage=round(
                        helpful / len(items) * 100.0,
                        3,
                    ),
                    harmful_percentage=round(
                        harmful / len(items) * 100.0,
                        3,
                    ),
                )
            )

        feature_consensus.sort(
            key=lambda item: (
                item.average_importance,
                item.helpful_percentage,
            ),
            reverse=True,
        )

        windows = tuple(
            V33FeatureWindowEvidence(
                offset=report.offset,
                limit=report.limit,
                matches_evaluated=(
                    report.matches_evaluated
                ),
                baseline_accuracy=(
                    report.baseline_accuracy
                ),
                baseline_brier_score=(
                    report.baseline_brier_score
                ),
                baseline_log_loss=(
                    report.baseline_log_loss
                ),
            )
            for report in reports
        )

        return V33MultiWindowEvidenceReport(
            model_version=reports[0].model_version,
            competition_code=competition_code,
            window_size=window_size,
            offsets=selected_offsets,
            windows_completed=len(reports),
            total_matches_evaluated=sum(
                report.matches_evaluated
                for report in reports
            ),
            windows=windows,
            features=tuple(feature_consensus),
        )

    @staticmethod
    def _average(values):
        usable = [
            float(value)
            for value in values
            if value is not None
        ]

        if not usable:
            return None

        return round(
            sum(usable) / len(usable),
            6,
        )
