from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_favourite_alignment_service import (
    CurrentMatchEnrichmentV33FavouriteAlignmentService,
)


@dataclass(frozen=True)
class V33FeatureReliabilityStabilityWindow:
    offset: int

    segment_matches: int
    segment_accuracy: Optional[float]

    supporting: int
    supporting_correct: int
    support_accuracy: Optional[float]

    average_support_strength: Optional[float]


@dataclass(frozen=True)
class V33FeatureReliabilityStabilityFeature:
    feature_name: str

    windows_with_evidence: int
    total_supporting: int

    average_support_accuracy: Optional[float]
    minimum_support_accuracy: Optional[float]
    maximum_support_accuracy: Optional[float]

    support_accuracy_range: Optional[float]

    segment_accuracy_correlation: Optional[float]

    windows: Tuple[
        V33FeatureReliabilityStabilityWindow,
        ...
    ]


@dataclass(frozen=True)
class V33FeatureReliabilityStabilityReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int

    offsets: Tuple[int, ...]

    windows_completed: int
    total_segment_matches: int

    features: Tuple[
        V33FeatureReliabilityStabilityFeature,
        ...
    ]


class CurrentMatchEnrichmentV33FeatureReliabilityStabilityService:
    """
    Independent cross-window reliability analysis for v3.3
    feature support.

    Windows are evaluated without pre-labelling them as strong
    or weak.

    For each feature, compare favourite-support accuracy with
    actual segment accuracy across windows.

    This service is read-only and does not modify v3.3.
    """

    def __init__(
        self,
        *,
        alignment_service=None,
    ) -> None:
        self.alignment_service = (
            alignment_service
            or CurrentMatchEnrichmentV33FavouriteAlignmentService()
        )

    def analyse(
        self,
        db: Session,
        *,
        offsets: Iterable[int],
        window_size: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_upper: int = 10,
        minimum_supporting: int = 5,
        competition_code: Optional[str] = "MODUS",
    ) -> V33FeatureReliabilityStabilityReport:
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

        if minimum_supporting <= 0:
            raise ValueError(
                "minimum_supporting must be greater than zero."
            )

        report = (
            self.alignment_service.analyse(
                db,
                offsets=offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                competition_code=competition_code,
            )
        )

        feature_names = sorted({
            item.feature_name
            for window in report.windows
            for item in window.feature_alignments
        })

        features = tuple(
            self._summarise_feature(
                feature_name,
                report.windows,
                minimum_supporting=minimum_supporting,
            )
            for feature_name in feature_names
        )

        return V33FeatureReliabilityStabilityReport(
            model_version=report.model_version,
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            offsets=offsets,
            windows_completed=len(
                report.windows
            ),
            total_segment_matches=(
                report.total_segment_matches
            ),
            features=features,
        )

    @classmethod
    def _summarise_feature(
        cls,
        feature_name,
        windows,
        *,
        minimum_supporting,
    ):
        rows = []

        for window in windows:
            alignment = next(
                (
                    item
                    for item
                    in window.feature_alignments
                    if item.feature_name
                    == feature_name
                ),
                None,
            )

            if alignment is None:
                continue

            rows.append(
                V33FeatureReliabilityStabilityWindow(
                    offset=window.offset,
                    segment_matches=(
                        window.segment_matches
                    ),
                    segment_accuracy=(
                        window.accuracy
                    ),
                    supporting=(
                        alignment.supporting
                    ),
                    supporting_correct=(
                        alignment.supporting_correct
                    ),
                    support_accuracy=(
                        alignment.support_accuracy
                    ),
                    average_support_strength=(
                        alignment
                        .average_support_strength
                    ),
                )
            )

        evidence = tuple(
            row
            for row in rows
            if (
                row.supporting
                >= minimum_supporting
                and row.support_accuracy
                is not None
                and row.segment_accuracy
                is not None
            )
        )

        support_accuracies = tuple(
            float(row.support_accuracy)
            for row in evidence
        )

        minimum_accuracy = (
            min(support_accuracies)
            if support_accuracies
            else None
        )

        maximum_accuracy = (
            max(support_accuracies)
            if support_accuracies
            else None
        )

        support_range = (
            round(
                maximum_accuracy
                - minimum_accuracy,
                6,
            )
            if (
                minimum_accuracy is not None
                and maximum_accuracy is not None
            )
            else None
        )

        return V33FeatureReliabilityStabilityFeature(
            feature_name=feature_name,
            windows_with_evidence=len(
                evidence
            ),
            total_supporting=sum(
                row.supporting
                for row in evidence
            ),
            average_support_accuracy=(
                cls._weighted_support_accuracy(
                    evidence
                )
            ),
            minimum_support_accuracy=(
                minimum_accuracy
            ),
            maximum_support_accuracy=(
                maximum_accuracy
            ),
            support_accuracy_range=(
                support_range
            ),
            segment_accuracy_correlation=(
                cls._correlation(
                    tuple(
                        float(
                            row.support_accuracy
                        )
                        for row in evidence
                    ),
                    tuple(
                        float(
                            row.segment_accuracy
                        )
                        for row in evidence
                    ),
                )
            ),
            windows=tuple(rows),
        )

    @staticmethod
    def _weighted_support_accuracy(
        rows,
    ):
        total = sum(
            int(row.supporting)
            for row in rows
        )

        if not total:
            return None

        correct = sum(
            int(row.supporting_correct)
            for row in rows
        )

        return round(
            float(correct)
            / float(total)
            * 100.0,
            3,
        )

    @staticmethod
    def _correlation(
        left,
        right,
    ):
        if len(left) != len(right):
            raise ValueError(
                "Correlation inputs must have equal lengths."
            )

        if len(left) < 3:
            return None

        mean_left = (
            sum(left)
            / len(left)
        )

        mean_right = (
            sum(right)
            / len(right)
        )

        numerator = sum(
            (
                x - mean_left
            )
            * (
                y - mean_right
            )
            for x, y
            in zip(
                left,
                right,
            )
        )

        left_squared = sum(
            (
                x - mean_left
            ) ** 2
            for x in left
        )

        right_squared = sum(
            (
                y - mean_right
            ) ** 2
            for y in right
        )

        denominator = sqrt(
            left_squared
            * right_squared
        )

        if denominator == 0.0:
            return None

        return round(
            numerator
            / denominator,
            6,
        )
