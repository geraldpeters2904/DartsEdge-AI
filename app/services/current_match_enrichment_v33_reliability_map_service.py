from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.current_match_enrichment_v33_history_depth_service import (
    CurrentMatchEnrichmentV33HistoryDepthService,
)
from app.services.current_match_enrichment_v33_segmentation_service import (
    CurrentMatchEnrichmentV33SegmentationService,
)
from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33ReliabilityCell:
    probability_band: str
    history_band: str

    predictions: int
    correct: int

    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]

    evidence_sufficient: bool
    reliability_score: Optional[float]


@dataclass(frozen=True)
class V33ReliabilityMapReport:
    model_version: str
    competition_code: Optional[str]

    offset: int
    limit: int
    matches_evaluated: int
    matches_skipped: int

    minimum_sample: int

    cells: Tuple[
        V33ReliabilityCell,
        ...
    ]

    strongest_cells: Tuple[
        V33ReliabilityCell,
        ...
    ]

    weakest_cells: Tuple[
        V33ReliabilityCell,
        ...
    ]


@dataclass(frozen=True)
class _ReliabilityRecord:
    correct: bool
    brier_score: float
    log_loss: float

    favourite_probability: float
    minimum_history: int


class CurrentMatchEnrichmentV33ReliabilityMapService:
    """
    Read-only joint reliability map for transparent-v3.3.

    Cells combine favourite-probability bands with minimum
    pre-match player-history bands.

    Only cells meeting minimum_sample are eligible for strongest
    and weakest rankings.
    """

    def __init__(
        self,
        *,
        snapshot_engine=None,
        prediction_engine=None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine
            or AdvancedHistoricalSnapshotEngine()
        )

        self.prediction_engine = (
            prediction_engine
            or TransparentPredictionEngineV33()
        )

    def analyse(
        self,
        db: Session,
        *,
        offset: int = 0,
        limit: int = 1500,
        minimum_sample: int = 30,
        ranking_count: int = 5,
        competition_code: Optional[str] = "MODUS",
    ) -> V33ReliabilityMapReport:
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if minimum_sample <= 0:
            raise ValueError(
                "minimum_sample must be greater than zero."
            )

        if ranking_count <= 0:
            raise ValueError(
                "ranking_count must be greater than zero."
            )

        match_ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=offset,
                limit=limit,
            )
        )

        records = []
        skipped = 0

        for match_id in match_ids:
            match = (
                db.query(Match)
                .filter(Match.id == match_id)
                .first()
            )

            if match is None:
                skipped += 1
                continue

            try:
                snapshot = (
                    self.snapshot_engine
                    .build_match_snapshot(
                        db,
                        match_id,
                        competition_code=competition_code,
                    )
                )

                prediction = (
                    self.prediction_engine
                    .predict(snapshot)
                )

                minimum_history = min(
                    int(
                        snapshot.player_a
                        .advanced_features
                        .matches_available
                    ),
                    int(
                        snapshot.player_b
                        .advanced_features
                        .matches_available
                    ),
                )

                favourite_probability = max(
                    float(
                        prediction.player_a_probability
                    ),
                    float(
                        prediction.player_b_probability
                    ),
                )

                actual_a = (
                    match.winner
                    == match.player_a
                )

                probability_a = (
                    float(
                        prediction.player_a_probability
                    )
                    / 100.0
                )

                actual_probability = (
                    probability_a
                    if actual_a
                    else 1.0 - probability_a
                )

                records.append(
                    _ReliabilityRecord(
                        correct=(
                            prediction.predicted_winner
                            == match.winner
                        ),
                        brier_score=round(
                            (
                                probability_a
                                - float(actual_a)
                            ) ** 2,
                            6,
                        ),
                        log_loss=self._log_loss(
                            actual_probability
                        ),
                        favourite_probability=(
                            favourite_probability
                        ),
                        minimum_history=(
                            minimum_history
                        ),
                    )
                )

            except (ValueError, LookupError):
                skipped += 1

        cells = []

        for probability_lower, probability_upper in (
            CurrentMatchEnrichmentV33SegmentationService
            .PROBABILITY_BANDS
        ):
            for history_lower, history_upper in (
                CurrentMatchEnrichmentV33HistoryDepthService
                .MINIMUM_HISTORY_BANDS
            ):
                cells.append(
                    self._build_cell(
                        records,
                        probability_lower=(
                            probability_lower
                        ),
                        probability_upper=(
                            probability_upper
                        ),
                        history_lower=(
                            history_lower
                        ),
                        history_upper=(
                            history_upper
                        ),
                        minimum_sample=minimum_sample,
                    )
                )

        eligible = [
            cell
            for cell in cells
            if cell.evidence_sufficient
        ]

        strongest = sorted(
            eligible,
            key=lambda cell: (
                -(
                    cell.reliability_score
                    if cell.reliability_score
                    is not None
                    else float("-inf")
                ),
                -cell.predictions,
                cell.probability_band,
                cell.history_band,
            ),
        )[:ranking_count]

        weakest = sorted(
            eligible,
            key=lambda cell: (
                (
                    cell.reliability_score
                    if cell.reliability_score
                    is not None
                    else float("inf")
                ),
                -cell.predictions,
                cell.probability_band,
                cell.history_band,
            ),
        )[:ranking_count]

        return V33ReliabilityMapReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            offset=offset,
            limit=limit,
            matches_evaluated=len(records),
            matches_skipped=skipped,
            minimum_sample=minimum_sample,
            cells=tuple(cells),
            strongest_cells=tuple(strongest),
            weakest_cells=tuple(weakest),
        )

    @classmethod
    def _build_cell(
        cls,
        records,
        *,
        probability_lower,
        probability_upper,
        history_lower,
        history_upper,
        minimum_sample,
    ):
        selected = tuple(
            record
            for record in records
            if (
                record.favourite_probability
                >= probability_lower
                and record.favourite_probability
                < probability_upper
                and record.minimum_history
                >= history_lower
                and (
                    history_upper is None
                    or record.minimum_history
                    < history_upper
                )
            )
        )

        predictions = len(selected)

        correct = sum(
            int(item.correct)
            for item in selected
        )

        accuracy = (
            cls._percentage(
                correct,
                predictions,
            )
            if predictions
            else None
        )

        brier = cls._average(
            item.brier_score
            for item in selected
        )

        log_loss = cls._average(
            item.log_loss
            for item in selected
        )

        sufficient = (
            predictions >= minimum_sample
        )

        score = (
            cls._reliability_score(
                accuracy=accuracy,
                brier=brier,
                log_loss=log_loss,
            )
            if sufficient
            else None
        )

        return V33ReliabilityCell(
            probability_band=(
                cls._probability_label(
                    probability_lower,
                    probability_upper,
                )
            ),
            history_band=(
                cls._history_label(
                    history_lower,
                    history_upper,
                )
            ),
            predictions=predictions,
            correct=correct,
            accuracy=accuracy,
            average_brier_score=brier,
            average_log_loss=log_loss,
            evidence_sufficient=sufficient,
            reliability_score=score,
        )

    @staticmethod
    def _reliability_score(
        *,
        accuracy,
        brier,
        log_loss,
    ):
        if (
            accuracy is None
            or brier is None
            or log_loss is None
        ):
            return None

        accuracy_component = (
            float(accuracy)
            / 100.0
        )

        brier_component = (
            1.0 - min(
                max(float(brier), 0.0),
                1.0,
            )
        )

        log_loss_component = (
            1.0 - min(
                max(
                    float(log_loss)
                    / 1.5,
                    0.0,
                ),
                1.0,
            )
        )

        return round(
            (
                accuracy_component
                + brier_component
                + log_loss_component
            )
            / 3.0,
            6,
        )

    @staticmethod
    def _probability_label(
        lower,
        upper,
    ):
        return (
            f"{lower}-100"
            if upper == 101
            else f"{lower}-{upper}"
        )

    @staticmethod
    def _history_label(
        lower,
        upper,
    ):
        return (
            f"{lower}+"
            if upper is None
            else f"{lower}-{upper - 1}"
        )

    @staticmethod
    def _average(values):
        values = tuple(
            float(value)
            for value in values
        )

        if not values:
            return None

        return round(
            sum(values) / len(values),
            6,
        )

    @staticmethod
    def _percentage(
        numerator,
        denominator,
    ):
        if denominator == 0:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )

    @staticmethod
    def _log_loss(
        actual_probability,
    ):
        from math import log

        clipped = min(
            max(
                float(actual_probability),
                1e-9,
            ),
            1.0 - 1e-9,
        )

        return round(
            -log(clipped),
            6,
        )
