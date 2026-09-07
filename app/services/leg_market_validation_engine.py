from __future__ import annotations

import re

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional, Tuple

from app.models.match import Match
from app.services.match_engine import leg_win_probability
from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)
from app.services.simulation_service import (
    handicap_cover_probability,
    simulate_match,
    total_legs_over_probability,
)


@dataclass(frozen=True)
class LegMarketValidationRecord:
    match_id: int
    player_a_leg_win_probability: float
    player_a_handicap_probability: float
    player_a_handicap_result: int
    total_legs_over_probability: float
    total_legs_over_result: int
    player_a_average: Optional[float] = None
    player_a_checkout: Optional[float] = None
    player_b_average: Optional[float] = None
    player_b_checkout: Optional[float] = None


@dataclass(frozen=True)
class CalibrationBucket:
    lower_bound: int
    upper_bound: int
    predictions: int
    mean_probability: Optional[float]
    observed_hit_rate: Optional[float]


@dataclass(frozen=True)
class LegMarketValidationReport:
    matches_considered: int
    matches_evaluated: int
    matches_skipped: int
    handicap_brier_score: Optional[float]
    total_legs_brier_score: Optional[float]
    handicap_calibration: Tuple[CalibrationBucket, ...]
    total_legs_calibration: Tuple[CalibrationBucket, ...]
    records: Tuple[LegMarketValidationRecord, ...]


class LegMarketValidationEngine:
    """
    Read-only historical validation for leg-derived markets.

    Probabilities are built from the pre-match snapshot so later match
    performances cannot leak into the historical prediction.
    """

    def __init__(
        self,
        *,
        snapshot_engine: Optional[PredictionSnapshotEngine] = None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine or PredictionSnapshotEngine()
        )

    def validate_matches(
        self,
        db,
        *,
        handicap_line=-1.5,
        total_legs_line=5.5,
        competition_code=None,
    ) -> LegMarketValidationReport:
        matches = (
            db.query(Match)
            .filter(Match.status == "completed")
            .order_by(Match.date.asc(), Match.id.asc())
            .all()
        )

        records = []

        for match in matches:
            result = self._validate_match(
                db,
                match,
                handicap_line=float(handicap_line),
                total_legs_line=float(total_legs_line),
                competition_code=competition_code,
            )
            if result is not None:
                records.append(result)

        return LegMarketValidationReport(
            matches_considered=len(matches),
            matches_evaluated=len(records),
            matches_skipped=len(matches) - len(records),
            handicap_brier_score=self._brier_score(
                records,
                probability_attr="player_a_handicap_probability",
                result_attr="player_a_handicap_result",
            ),
            total_legs_brier_score=self._brier_score(
                records,
                probability_attr="total_legs_over_probability",
                result_attr="total_legs_over_result",
            ),
            handicap_calibration=self._calibration(
                records,
                probability_attr="player_a_handicap_probability",
                result_attr="player_a_handicap_result",
            ),
            total_legs_calibration=self._calibration(
                records,
                probability_attr="total_legs_over_probability",
                result_attr="total_legs_over_result",
            ),
            records=tuple(records),
        )

    def _validate_match(
        self,
        db,
        match,
        *,
        handicap_line,
        total_legs_line,
        competition_code,
    ):
        score = self._score(match)
        best_of = self._best_of(match.match_format)

        if score is None or best_of is None:
            return None

        legs_a, legs_b = score

        expected_winner = (
            match.player_a
            if legs_a > legs_b
            else match.player_b
        )

        if (
            legs_a == legs_b
            or match.winner != expected_winner
        ):
            return None

        snapshot = self.snapshot_engine.build_match_snapshot(
            db,
            match.id,
            competition_code=competition_code,
        )

        average_a = snapshot.player_a.last_10_average
        checkout_a = (
            snapshot.player_a.last_10_checkout_percentage
        )
        average_b = snapshot.player_b.last_10_average
        checkout_b = (
            snapshot.player_b.last_10_checkout_percentage
        )

        if any(
            value is None or float(value) <= 0
            for value in (
                average_a,
                checkout_a,
                average_b,
                checkout_b,
            )
        ):
            return None

        profile_a = SimpleNamespace(
            average=float(average_a),
            checkout=float(checkout_a),
        )
        profile_b = SimpleNamespace(
            average=float(average_b),
            checkout=float(checkout_b),
        )

        leg_probability_a = leg_win_probability(
            profile_a,
            profile_b,
        )

        simulation = simulate_match(
            profile_a,
            profile_b,
            leg_win_prob_a=leg_probability_a,
            best_of=best_of,
        )

        handicap_probability = handicap_cover_probability(
            simulation,
            player="a",
            line=handicap_line,
        )
        total_probability = total_legs_over_probability(
            simulation,
            line=total_legs_line,
        )

        return LegMarketValidationRecord(
            match_id=match.id,
            player_a_leg_win_probability=leg_probability_a,
            player_a_handicap_probability=handicap_probability,
            player_a_handicap_result=int(
                (legs_a + handicap_line) > legs_b
            ),
            total_legs_over_probability=total_probability,
            total_legs_over_result=int(
                (legs_a + legs_b) > total_legs_line
            ),
            player_a_average=float(average_a),
            player_a_checkout=float(checkout_a),
            player_b_average=float(average_b),
            player_b_checkout=float(checkout_b),
        )

    @staticmethod
    def _brier_score(
        records,
        *,
        probability_attr,
        result_attr,
    ):
        if not records:
            return None

        return sum(
            (
                float(getattr(record, probability_attr))
                - int(getattr(record, result_attr))
            ) ** 2
            for record in records
        ) / len(records)

    @staticmethod
    def _calibration(
        records,
        *,
        probability_attr,
        result_attr,
    ):
        buckets = []

        for lower_bound in range(0, 100, 10):
            upper_bound = lower_bound + 10

            values = [
                (
                    float(getattr(record, probability_attr)),
                    int(getattr(record, result_attr)),
                )
                for record in records
                if (
                    lower_bound
                    <= float(getattr(record, probability_attr)) * 100
                    < upper_bound
                )
                or (
                    upper_bound == 100
                    and float(getattr(record, probability_attr)) == 1.0
                )
            ]

            if values:
                mean_probability = (
                    sum(probability for probability, _ in values)
                    / len(values)
                    * 100
                )
                observed_hit_rate = (
                    sum(result for _, result in values)
                    / len(values)
                    * 100
                )
            else:
                mean_probability = None
                observed_hit_rate = None

            buckets.append(
                CalibrationBucket(
                    lower_bound=lower_bound,
                    upper_bound=upper_bound,
                    predictions=len(values),
                    mean_probability=mean_probability,
                    observed_hit_rate=observed_hit_rate,
                )
            )

        return tuple(buckets)

    @staticmethod
    def _score(match):
        if not getattr(match, "score", None):
            return None

        parts = match.score.split("-")
        if (
            len(parts) != 2
            or not all(part.isdigit() for part in parts)
        ):
            return None

        return int(parts[0]), int(parts[1])

    @staticmethod
    def _best_of(match_format):
        if not match_format:
            return None

        match = re.search(
            r"Best of (\d+)",
            str(match_format),
            re.IGNORECASE,
        )
        if match is None:
            return None

        best_of = int(match.group(1))
        if best_of <= 0 or best_of % 2 == 0:
            return None

        return best_of
