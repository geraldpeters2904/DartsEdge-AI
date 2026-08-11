from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.current_match_enrichment_v33_wrong_consensus_service import (
    CurrentMatchEnrichmentV33WrongConsensusService,
)


@dataclass(frozen=True)
class V33WrongConsensusAggregateFeature:
    feature_name: str

    correct_supporting: int
    incorrect_supporting: int

    support_rate_correct: Optional[float]
    support_rate_incorrect: Optional[float]

    support_rate_gap: Optional[float]

    correct_average_support_strength: Optional[float]
    incorrect_average_support_strength: Optional[float]

    support_strength_gap: Optional[float]


@dataclass(frozen=True)
class V33WrongConsensusAggregateReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int
    agreement_lower: float

    total_high_agreement_matches: int
    total_correct_high_agreement: int
    total_incorrect_high_agreement: int

    features: Tuple[
        V33WrongConsensusAggregateFeature,
        ...
    ]


class CurrentMatchEnrichmentV33WrongConsensusAggregateService:
    """
    Aggregate high-consensus correct-vs-incorrect feature support
    across multiple windows.

    This service delegates historical evaluation to the existing
    wrong-consensus diagnostic and performs aggregation only.

    It is read-only and does not modify transparent-v3.3.
    """

    def __init__(
        self,
        *,
        wrong_consensus_service=None,
    ) -> None:
        self.wrong_consensus_service = (
            wrong_consensus_service
            or CurrentMatchEnrichmentV33WrongConsensusService()
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
        agreement_lower: float = 80.0,
        competition_code: Optional[str] = "MODUS",
    ) -> V33WrongConsensusAggregateReport:
        offsets = tuple(
            int(value)
            for value in offsets
        )

        if not offsets:
            raise ValueError(
                "Enter at least one window offset."
            )

        report = (
            self.wrong_consensus_service.analyse(
                db,
                offsets=offsets,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                agreement_lower=agreement_lower,
                competition_code=competition_code,
            )
        )

        aggregated = {}

        for window in report.windows:
            for item in window.features:
                bucket = aggregated.setdefault(
                    item.feature_name,
                    {
                        "correct_supporting": 0,
                        "incorrect_supporting": 0,
                        "correct_strength_total": 0.0,
                        "correct_strength_count": 0,
                        "incorrect_strength_total": 0.0,
                        "incorrect_strength_count": 0,
                    },
                )

                bucket["correct_supporting"] += (
                    int(item.correct_supporting)
                )

                bucket["incorrect_supporting"] += (
                    int(item.incorrect_supporting)
                )

                if (
                    item.correct_average_support_strength
                    is not None
                    and item.correct_supporting > 0
                ):
                    bucket[
                        "correct_strength_total"
                    ] += (
                        float(
                            item.correct_average_support_strength
                        )
                        * int(item.correct_supporting)
                    )

                    bucket[
                        "correct_strength_count"
                    ] += int(
                        item.correct_supporting
                    )

                if (
                    item.incorrect_average_support_strength
                    is not None
                    and item.incorrect_supporting > 0
                ):
                    bucket[
                        "incorrect_strength_total"
                    ] += (
                        float(
                            item.incorrect_average_support_strength
                        )
                        * int(item.incorrect_supporting)
                    )

                    bucket[
                        "incorrect_strength_count"
                    ] += int(
                        item.incorrect_supporting
                    )

        features = tuple(
            self._summarise_feature(
                feature_name,
                values,
                correct_total=(
                    report.total_correct_high_agreement
                ),
                incorrect_total=(
                    report.total_incorrect_high_agreement
                ),
            )
            for feature_name, values
            in sorted(
                aggregated.items()
            )
        )

        return V33WrongConsensusAggregateReport(
            model_version=report.model_version,
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            agreement_lower=agreement_lower,
            total_high_agreement_matches=(
                report.total_high_agreement_matches
            ),
            total_correct_high_agreement=(
                report.total_correct_high_agreement
            ),
            total_incorrect_high_agreement=(
                report.total_incorrect_high_agreement
            ),
            features=features,
        )

    @classmethod
    def _summarise_feature(
        cls,
        feature_name,
        values,
        *,
        correct_total,
        incorrect_total,
    ):
        correct_supporting = int(
            values["correct_supporting"]
        )

        incorrect_supporting = int(
            values["incorrect_supporting"]
        )

        correct_rate = cls._percentage(
            correct_supporting,
            correct_total,
        )

        incorrect_rate = cls._percentage(
            incorrect_supporting,
            incorrect_total,
        )

        correct_strength = cls._weighted_average(
            values[
                "correct_strength_total"
            ],
            values[
                "correct_strength_count"
            ],
        )

        incorrect_strength = cls._weighted_average(
            values[
                "incorrect_strength_total"
            ],
            values[
                "incorrect_strength_count"
            ],
        )

        return V33WrongConsensusAggregateFeature(
            feature_name=feature_name,
            correct_supporting=correct_supporting,
            incorrect_supporting=incorrect_supporting,
            support_rate_correct=correct_rate,
            support_rate_incorrect=incorrect_rate,
            support_rate_gap=cls._difference(
                incorrect_rate,
                correct_rate,
            ),
            correct_average_support_strength=(
                correct_strength
            ),
            incorrect_average_support_strength=(
                incorrect_strength
            ),
            support_strength_gap=cls._difference(
                incorrect_strength,
                correct_strength,
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
