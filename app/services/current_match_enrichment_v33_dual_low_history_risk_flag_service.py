from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Optional, Tuple

from sqlalchemy import or_

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class CurrentMatchEnrichmentV33RiskPopulation:
    name: str
    predictions: int
    correct: int
    accuracy: Optional[float]
    brier_score: Optional[float]
    log_loss: Optional[float]


@dataclass(frozen=True)
class CurrentMatchEnrichmentV33DualLowHistoryRiskFlagReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_threshold: int
    agreement_threshold: float

    matches_evaluated: int
    segment_matches: int
    flagged_matches: int
    filtered_matches: int

    coverage_retained: Optional[float]

    full_segment: CurrentMatchEnrichmentV33RiskPopulation
    flagged: CurrentMatchEnrichmentV33RiskPopulation
    filtered: CurrentMatchEnrichmentV33RiskPopulation

    flagged_match_ids: Tuple[int, ...]


class CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService:
    """
    Read-only diagnostic for the sparse-consensus risk signal.

    A prediction is flagged when:

    - favourite probability is inside the requested segment;
    - both players have fewer than history_threshold matches;
    - active non-zero feature contributions agree 100% with the
      predicted winner.

    The service compares the full segment, the flagged population,
    and the segment remaining after flagged predictions are removed.

    No model weights or warehouse data are modified.
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
        db,
        *,
        offset: int = 0,
        limit: int = 17000,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        agreement_threshold: float = 100.0,
        competition_code: Optional[str] = "MODUS",
    ):
        if offset < 0:
            raise ValueError(
                "offset cannot be negative."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        if probability_lower >= probability_upper:
            raise ValueError(
                "probability_lower must be less than probability_upper."
            )

        if history_threshold <= 0:
            raise ValueError(
                "history_threshold must be greater than zero."
            )

        if not 0.0 <= agreement_threshold <= 100.0:
            raise ValueError(
                "agreement_threshold must be between 0 and 100."
            )

        match_ids = self._select_match_ids(
            db,
            offset=offset,
            limit=limit,
        )

        segment_records = []
        flagged_records = []

        for match_id in match_ids:
            try:
                snapshot = (
                    self.snapshot_engine
                    .build_match_snapshot(
                        db,
                        match_id,
                        competition_code=competition_code,
                    )
                )
            except Exception:
                continue

            if snapshot is None:
                continue

            try:
                prediction = (
                    self.prediction_engine
                    .predict(snapshot)
                )
            except Exception:
                continue

            favourite_probability = max(
                prediction.player_a_probability,
                prediction.player_b_probability,
            )

            if not (
                probability_lower
                <= favourite_probability
                < probability_upper
            ):
                continue

            actual_winner = self._actual_winner(
                db,
                match_id,
            )

            if actual_winner is None:
                continue

            correct = (
                prediction.predicted_winner
                == actual_winner
            )

            probability_correct = (
                favourite_probability / 100.0
                if correct
                else 1.0 - (
                    favourite_probability / 100.0
                )
            )

            record = {
                "match_id": match_id,
                "correct": correct,
                "probability_correct": probability_correct,
            }

            segment_records.append(record)

            player_a_history = (
                snapshot.player_a
                .advanced_features
                .matches_available
            )

            player_b_history = (
                snapshot.player_b
                .advanced_features
                .matches_available
            )

            if not (
                player_a_history < history_threshold
                and player_b_history < history_threshold
            ):
                continue

            agreement = self._feature_agreement(
                prediction,
            )

            if agreement is None:
                continue

            if agreement < agreement_threshold:
                continue

            flagged_records.append(record)

        flagged_ids = {
            item["match_id"]
            for item in flagged_records
        }

        filtered_records = [
            item
            for item in segment_records
            if item["match_id"] not in flagged_ids
        ]

        full_population = self._population(
            "full_segment",
            segment_records,
        )

        flagged_population = self._population(
            "flagged",
            flagged_records,
        )

        filtered_population = self._population(
            "filtered",
            filtered_records,
        )

        coverage_retained = (
            round(
                len(filtered_records)
                / len(segment_records)
                * 100.0,
                3,
            )
            if segment_records
            else None
        )

        return (
            CurrentMatchEnrichmentV33DualLowHistoryRiskFlagReport(
                model_version=(
                    self.prediction_engine.MODEL_VERSION
                ),
                competition_code=competition_code,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                agreement_threshold=agreement_threshold,
                matches_evaluated=len(match_ids),
                segment_matches=len(segment_records),
                flagged_matches=len(flagged_records),
                filtered_matches=len(filtered_records),
                coverage_retained=coverage_retained,
                full_segment=full_population,
                flagged=flagged_population,
                filtered=filtered_population,
                flagged_match_ids=tuple(
                    item["match_id"]
                    for item in flagged_records
                ),
            )
        )

    @staticmethod
    def _feature_agreement(
        prediction,
    ) -> Optional[float]:
        supporting = 0
        opposing = 0

        predicted_a = (
            prediction.predicted_winner
            == prediction.player_a_name
        )

        for contribution in prediction.contributions:
            weighted_score = (
                contribution.weighted_score
            )

            if weighted_score == 0:
                continue

            supports_prediction = (
                weighted_score > 0
                if predicted_a
                else weighted_score < 0
            )

            if supports_prediction:
                supporting += 1
            else:
                opposing += 1

        total = supporting + opposing

        if total == 0:
            return None

        return round(
            supporting / total * 100.0,
            6,
        )

    @staticmethod
    def _population(
        name,
        records,
    ):
        n = len(records)

        if not n:
            return (
                CurrentMatchEnrichmentV33RiskPopulation(
                    name=name,
                    predictions=0,
                    correct=0,
                    accuracy=None,
                    brier_score=None,
                    log_loss=None,
                )
            )

        correct = sum(
            1
            for item in records
            if item["correct"]
        )

        accuracy = round(
            correct / n * 100.0,
            3,
        )

        brier_values = []
        log_loss_values = []

        for item in records:
            probability_correct = min(
                max(
                    item["probability_correct"],
                    1e-15,
                ),
                1.0 - 1e-15,
            )

            probability_favourite = (
                probability_correct
                if item["correct"]
                else 1.0 - probability_correct
            )

            outcome = (
                1.0
                if item["correct"]
                else 0.0
            )

            brier_values.append(
                (
                    probability_favourite
                    - outcome
                ) ** 2
            )

            log_loss_values.append(
                -log(probability_correct)
            )

        return (
            CurrentMatchEnrichmentV33RiskPopulation(
                name=name,
                predictions=n,
                correct=correct,
                accuracy=accuracy,
                brier_score=round(
                    sum(brier_values)
                    / n,
                    6,
                ),
                log_loss=round(
                    sum(log_loss_values)
                    / n,
                    6,
                ),
            )
        )

    @staticmethod
    def _actual_winner(
        db,
        match_id,
    ):
        row = (
            db.query(Match.winner)
            .filter(
                Match.id == match_id
            )
            .first()
        )

        if row is None:
            return None

        return row[0]

    @staticmethod
    def _select_match_ids(
        db,
        *,
        offset,
        limit,
    ):
        rows = (
            db.query(Match.id)
            .filter(
                Match.status == "completed",
                Match.winner.isnot(None),
                or_(
                    Match.winner == Match.player_a,
                    Match.winner == Match.player_b,
                ),
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
