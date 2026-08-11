from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_favourite_alignment_service import (
    CurrentMatchEnrichmentV33FavouriteAlignmentService,
)


@dataclass(frozen=True)
class V33FeatureReliabilityComparison:
    feature_name: str

    strong_supporting: int
    strong_supporting_correct: int
    strong_support_accuracy: Optional[float]
    strong_average_support_strength: Optional[float]

    weak_supporting: int
    weak_supporting_correct: int
    weak_support_accuracy: Optional[float]
    weak_average_support_strength: Optional[float]

    support_accuracy_change: Optional[float]
    reliability_deterioration: Optional[float]


@dataclass(frozen=True)
class V33FeatureReliabilityReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int

    strong_offsets: Tuple[int, ...]
    weak_offsets: Tuple[int, ...]

    strong_segment_matches: int
    weak_segment_matches: int

    features: Tuple[
        V33FeatureReliabilityComparison,
        ...
    ]


class CurrentMatchEnrichmentV33FeatureReliabilityService:
    """
    Compare favourite-support reliability for v3.3 features
    between strong and weak low-history historical regimes.

    This service delegates historical evaluation to the existing
    favourite-alignment diagnostic and performs aggregation only.

    It does not modify model weights or probabilities.
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
        strong_offsets: Iterable[int],
        weak_offsets: Iterable[int],
        window_size: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_upper: int = 10,
        competition_code: Optional[str] = "MODUS",
    ) -> V33FeatureReliabilityReport:
        strong_offsets = tuple(
            int(value)
            for value in strong_offsets
        )

        weak_offsets = tuple(
            int(value)
            for value in weak_offsets
        )

        if not strong_offsets:
            raise ValueError(
                "Enter at least one strong-regime offset."
            )

        if not weak_offsets:
            raise ValueError(
                "Enter at least one weak-regime offset."
            )

        overlap = set(
            strong_offsets
        ).intersection(
            weak_offsets
        )

        if overlap:
            raise ValueError(
                "Strong and weak regime offsets cannot overlap."
            )

        strong_report = (
            self.alignment_service.analyse(
                db,
                offsets=strong_offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                competition_code=competition_code,
            )
        )

        weak_report = (
            self.alignment_service.analyse(
                db,
                offsets=weak_offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                competition_code=competition_code,
            )
        )

        strong = self._aggregate_features(
            strong_report
        )

        weak = self._aggregate_features(
            weak_report
        )

        feature_names = sorted(
            set(strong)
            | set(weak)
        )

        features = tuple(
            self._compare_feature(
                feature_name,
                strong.get(feature_name),
                weak.get(feature_name),
            )
            for feature_name
            in feature_names
        )

        return V33FeatureReliabilityReport(
            model_version=(
                strong_report.model_version
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            strong_offsets=strong_offsets,
            weak_offsets=weak_offsets,
            strong_segment_matches=(
                strong_report
                .total_segment_matches
            ),
            weak_segment_matches=(
                weak_report
                .total_segment_matches
            ),
            features=features,
        )

    @classmethod
    def _aggregate_features(
        cls,
        report,
    ):
        values = {}

        for window in report.windows:
            for item in window.feature_alignments:
                bucket = values.setdefault(
                    item.feature_name,
                    {
                        "supporting": 0,
                        "supporting_correct": 0,
                        "support_strength_total": 0.0,
                        "support_strength_count": 0,
                    },
                )

                bucket["supporting"] += (
                    int(item.supporting)
                )

                bucket["supporting_correct"] += (
                    int(
                        item.supporting_correct
                    )
                )

                if (
                    item.average_support_strength
                    is not None
                    and item.supporting > 0
                ):
                    bucket[
                        "support_strength_total"
                    ] += (
                        float(
                            item.average_support_strength
                        )
                        * int(item.supporting)
                    )

                    bucket[
                        "support_strength_count"
                    ] += int(
                        item.supporting
                    )

        return values

    @classmethod
    def _compare_feature(
        cls,
        feature_name,
        strong,
        weak,
    ):
        strong = strong or {
            "supporting": 0,
            "supporting_correct": 0,
            "support_strength_total": 0.0,
            "support_strength_count": 0,
        }

        weak = weak or {
            "supporting": 0,
            "supporting_correct": 0,
            "support_strength_total": 0.0,
            "support_strength_count": 0,
        }

        strong_accuracy = cls._percentage(
            strong["supporting_correct"],
            strong["supporting"],
        )

        weak_accuracy = cls._percentage(
            weak["supporting_correct"],
            weak["supporting"],
        )

        change = cls._difference(
            weak_accuracy,
            strong_accuracy,
        )

        deterioration = (
            -change
            if change is not None
            and change < 0
            else 0.0
            if change is not None
            else None
        )

        return V33FeatureReliabilityComparison(
            feature_name=feature_name,
            strong_supporting=(
                strong["supporting"]
            ),
            strong_supporting_correct=(
                strong[
                    "supporting_correct"
                ]
            ),
            strong_support_accuracy=(
                strong_accuracy
            ),
            strong_average_support_strength=(
                cls._weighted_average(
                    strong[
                        "support_strength_total"
                    ],
                    strong[
                        "support_strength_count"
                    ],
                )
            ),
            weak_supporting=(
                weak["supporting"]
            ),
            weak_supporting_correct=(
                weak[
                    "supporting_correct"
                ]
            ),
            weak_support_accuracy=(
                weak_accuracy
            ),
            weak_average_support_strength=(
                cls._weighted_average(
                    weak[
                        "support_strength_total"
                    ],
                    weak[
                        "support_strength_count"
                    ],
                )
            ),
            support_accuracy_change=change,
            reliability_deterioration=(
                deterioration
            ),
        )

    @staticmethod
    def _weighted_average(
        total,
        count,
    ):
        if not count:
            return None

        return round(
            float(total)
            / float(count),
            6,
        )

    @staticmethod
    def _percentage(
        numerator,
        denominator,
    ):
        if not denominator:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )

    @staticmethod
    def _difference(
        left,
        right,
    ):
        if left is None or right is None:
            return None

        return round(
            float(left)
            - float(right),
            6,
        )
