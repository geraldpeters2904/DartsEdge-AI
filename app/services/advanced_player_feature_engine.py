from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import pstdev
from typing import Dict, Iterable, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)


@dataclass(frozen=True)
class AdvancedRollingWindow:
    label: str
    requested_matches: Optional[int]
    matches: int

    wins: int
    losses: int
    win_percentage: Optional[float]

    legs_won: int
    legs_lost: int
    leg_difference: int
    legs_played: int

    average_three_dart_average: Optional[float]
    average_first_nine_average: Optional[float]

    scores_100_plus_per_match: Optional[float]
    scores_140_plus_per_match: Optional[float]
    scores_180_per_match: Optional[float]

    scores_100_plus_per_leg: Optional[float]
    scores_140_plus_per_leg: Optional[float]
    scores_180_per_leg: Optional[float]

    checkout_attempts: int
    checkouts_completed: int
    checkout_percentage: Optional[float]
    checkout_attempts_per_leg: Optional[float]

    highest_checkout: Optional[int]
    average_highest_checkout: Optional[float]

    threw_first_matches: int
    threw_first_wins: int
    threw_first_win_percentage: Optional[float]

    threw_second_matches: int
    threw_second_wins: int
    threw_second_win_percentage: Optional[float]

    deciding_matches: int
    deciding_wins: int
    deciding_win_percentage: Optional[float]


@dataclass(frozen=True)
class TrendSignal:
    metric: str
    recent_value: Optional[float]
    baseline_value: Optional[float]
    absolute_change: Optional[float]
    percentage_change: Optional[float]
    direction: str


@dataclass(frozen=True)
class FatigueContext:
    latest_observed_at: Optional[str]
    matches_on_latest_day: int
    legs_on_latest_day: int
    hours_since_previous_match: Optional[float]
    days_since_previous_match: Optional[int]


@dataclass(frozen=True)
class ConsistencyProfile:
    sample_matches: int
    three_dart_average_stddev: Optional[float]
    checkout_percentage_stddev: Optional[float]
    scores_180_stddev: Optional[float]


@dataclass(frozen=True)
class AdvancedPlayerFeatureProfile:
    player_id: int
    competition_code: Optional[str]
    matches_available: int
    latest_match_id: Optional[int]
    latest_match_date: Optional[str]

    windows: Dict[str, AdvancedRollingWindow]
    trends: Tuple[TrendSignal, ...]
    fatigue: FatigueContext
    consistency: Optional[ConsistencyProfile] = None


class AdvancedPlayerFeatureEngine:
    """
    Read-only advanced feature derivation for prediction research.

    Windows are calculated newest-first from immutable player performances.
    No warehouse, Player, Match or performance rows are changed.
    """

    WINDOW_DEFINITIONS = (
        ("last_5", 5),
        ("last_10", 10),
        ("last_20", 20),
        ("last_50", 50),
        ("career", None),
    )

    def build_player_profile(
        self,
        db: Session,
        player_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> AdvancedPlayerFeatureProfile:
        rows = self._load_rows(
            db,
            player_id=player_id,
            competition_code=competition_code,
        )
        return self.build_from_rows(
            player_id=player_id,
            rows=rows,
            competition_code=competition_code,
        )

    def build_from_rows(
        self,
        *,
        player_id: int,
        rows: Sequence[Tuple[object, object]],
        competition_code: Optional[str] = None,
    ) -> AdvancedPlayerFeatureProfile:
        performances = [performance for performance, _match in rows]
        latest_match = rows[0][1] if rows else None

        windows = {}
        for label, requested in self.WINDOW_DEFINITIONS:
            selected = (
                performances
                if requested is None
                else performances[:requested]
            )
            windows[label] = self._build_window(
                label=label,
                requested_matches=requested,
                performances=selected,
            )

        trends = (
            self._trend(
                "three_dart_average",
                windows["last_5"].average_three_dart_average,
                windows["last_20"].average_three_dart_average,
            ),
            self._trend(
                "checkout_percentage",
                windows["last_5"].checkout_percentage,
                windows["last_20"].checkout_percentage,
            ),
            self._trend(
                "scores_180_per_match",
                windows["last_5"].scores_180_per_match,
                windows["last_20"].scores_180_per_match,
            ),
            self._trend(
                "win_percentage",
                windows["last_5"].win_percentage,
                windows["last_20"].win_percentage,
            ),
        )

        return AdvancedPlayerFeatureProfile(
            player_id=player_id,
            competition_code=competition_code,
            matches_available=len(performances),
            latest_match_id=(
                latest_match.id
                if latest_match is not None
                else None
            ),
            latest_match_date=(
                latest_match.date.isoformat()
                if (
                    latest_match is not None
                    and latest_match.date is not None
                )
                else None
            ),
            windows=windows,
            trends=trends,
            fatigue=self._fatigue_context(rows),
            consistency=self._consistency_profile(
                performances[:10]
            ),
        )

    @classmethod
    def _consistency_profile(
        cls,
        performances,
    ) -> ConsistencyProfile:
        return ConsistencyProfile(
            sample_matches=len(performances),
            three_dart_average_stddev=(
                cls._standard_deviation(
                    item.three_dart_average
                    for item in performances
                    if item.three_dart_average
                    is not None
                )
            ),
            checkout_percentage_stddev=(
                cls._standard_deviation(
                    item.checkout_percentage
                    for item in performances
                    if item.checkout_percentage
                    is not None
                )
            ),
            scores_180_stddev=(
                cls._standard_deviation(
                    item.scores_180
                    for item in performances
                    if item.scores_180 is not None
                )
            ),
        )

    @staticmethod
    def _standard_deviation(
        values,
    ) -> Optional[float]:
        available = [
            float(value)
            for value in values
        ]

        if len(available) < 2:
            return None

        return round(
            pstdev(available),
            6,
        )

    def _load_rows(
        self,
        db: Session,
        *,
        player_id: int,
        competition_code: Optional[str],
    ):
        query = (
            db.query(PlayerMatchPerformance, Match)
            .join(
                Match,
                Match.id == PlayerMatchPerformance.match_id,
            )
            .filter(
                PlayerMatchPerformance.player_id == player_id
            )
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        return query.order_by(
            Match.date.desc(),
            PlayerMatchPerformance.observed_at.desc(),
            PlayerMatchPerformance.created_at.desc(),
            PlayerMatchPerformance.id.desc(),
        ).all()

    def _build_window(
        self,
        *,
        label: str,
        requested_matches: Optional[int],
        performances,
    ) -> AdvancedRollingWindow:
        matches = len(performances)
        wins = sum(1 for item in performances if item.won_match is True)
        losses = sum(1 for item in performances if item.won_match is False)

        legs_won = sum(item.legs_won or 0 for item in performances)
        legs_lost = sum(item.legs_lost or 0 for item in performances)
        legs_played = legs_won + legs_lost

        checkout_rows = [
            item
            for item in performances
            if (
                item.checkout_attempts is not None
                and item.checkouts_completed is not None
            )
        ]
        attempts = sum(item.checkout_attempts or 0 for item in checkout_rows)
        completed = sum(item.checkouts_completed or 0 for item in checkout_rows)

        highest_values = [
            item.highest_checkout
            for item in performances
            if item.highest_checkout is not None
        ]

        threw_first_rows = [
            item for item in performances
            if item.threw_first is True
        ]
        threw_second_rows = [
            item for item in performances
            if item.threw_first is False
        ]

        deciding_rows = [
            item
            for item in performances
            if self._is_deciding_match(item)
        ]

        return AdvancedRollingWindow(
            label=label,
            requested_matches=requested_matches,
            matches=matches,
            wins=wins,
            losses=losses,
            win_percentage=self._percentage_or_none(wins, matches),
            legs_won=legs_won,
            legs_lost=legs_lost,
            leg_difference=legs_won - legs_lost,
            legs_played=legs_played,
            average_three_dart_average=self._average(
                item.three_dart_average for item in performances
            ),
            average_first_nine_average=self._average(
                item.first_nine_average for item in performances
            ),
            scores_100_plus_per_match=self._per_match(
                (item.scores_100_plus for item in performances),
                matches,
            ),
            scores_140_plus_per_match=self._per_match(
                (item.scores_140_plus for item in performances),
                matches,
            ),
            scores_180_per_match=self._per_match(
                (item.scores_180 for item in performances),
                matches,
            ),
            scores_100_plus_per_leg=self._per_leg(
                (item.scores_100_plus for item in performances),
                legs_played,
            ),
            scores_140_plus_per_leg=self._per_leg(
                (item.scores_140_plus for item in performances),
                legs_played,
            ),
            scores_180_per_leg=self._per_leg(
                (item.scores_180 for item in performances),
                legs_played,
            ),
            checkout_attempts=attempts,
            checkouts_completed=completed,
            checkout_percentage=(
                self._percentage_or_none(completed, attempts)
            ),
            checkout_attempts_per_leg=(
                round(attempts / legs_played, 3)
                if legs_played
                else None
            ),
            highest_checkout=max(highest_values) if highest_values else None,
            average_highest_checkout=self._average(highest_values),
            threw_first_matches=len(threw_first_rows),
            threw_first_wins=sum(
                1 for item in threw_first_rows
                if item.won_match is True
            ),
            threw_first_win_percentage=self._percentage_or_none(
                sum(
                    1 for item in threw_first_rows
                    if item.won_match is True
                ),
                len(threw_first_rows),
            ),
            threw_second_matches=len(threw_second_rows),
            threw_second_wins=sum(
                1 for item in threw_second_rows
                if item.won_match is True
            ),
            threw_second_win_percentage=self._percentage_or_none(
                sum(
                    1 for item in threw_second_rows
                    if item.won_match is True
                ),
                len(threw_second_rows),
            ),
            deciding_matches=len(deciding_rows),
            deciding_wins=sum(
                1 for item in deciding_rows
                if item.won_match is True
            ),
            deciding_win_percentage=self._percentage_or_none(
                sum(
                    1 for item in deciding_rows
                    if item.won_match is True
                ),
                len(deciding_rows),
            ),
        )

    @staticmethod
    def _is_deciding_match(performance) -> bool:
        if (
            performance.legs_won is None
            or performance.legs_lost is None
        ):
            return False

        return abs(
            performance.legs_won
            - performance.legs_lost
        ) == 1

    @staticmethod
    def _trend(
        metric: str,
        recent: Optional[float],
        baseline: Optional[float],
    ) -> TrendSignal:
        if recent is None or baseline is None:
            return TrendSignal(
                metric=metric,
                recent_value=recent,
                baseline_value=baseline,
                absolute_change=None,
                percentage_change=None,
                direction="unknown",
            )

        change = recent - baseline

        if abs(change) < 0.001:
            direction = "flat"
        elif change > 0:
            direction = "improving"
        else:
            direction = "declining"

        percentage_change = (
            change / abs(baseline) * 100
            if baseline != 0
            else None
        )

        return TrendSignal(
            metric=metric,
            recent_value=round(recent, 3),
            baseline_value=round(baseline, 3),
            absolute_change=round(change, 3),
            percentage_change=(
                round(percentage_change, 3)
                if percentage_change is not None
                else None
            ),
            direction=direction,
        )

    @staticmethod
    def _fatigue_context(
        rows: Sequence[Tuple[object, object]],
    ) -> FatigueContext:
        if not rows:
            return FatigueContext(
                latest_observed_at=None,
                matches_on_latest_day=0,
                legs_on_latest_day=0,
                hours_since_previous_match=None,
                days_since_previous_match=None,
            )

        latest_performance, latest_match = rows[0]
        latest_date = getattr(latest_match, "date", None)
        latest_observed = getattr(
            latest_performance,
            "observed_at",
            None,
        )

        same_day = [
            performance
            for performance, match in rows
            if (
                latest_date is not None
                and getattr(match, "date", None) == latest_date
            )
        ]

        previous_observed = next(
            (
                getattr(performance, "observed_at", None)
                for performance, _match in rows[1:]
                if (
                    getattr(performance, "observed_at", None)
                    is not None
                    and latest_observed is not None
                    and getattr(performance, "observed_at", None)
                    < latest_observed
                )
            ),
            None,
        )

        hours_since = (
            round(
                (
                    latest_observed
                    - previous_observed
                ).total_seconds()
                / 3600,
                3,
            )
            if (
                latest_observed is not None
                and previous_observed is not None
            )
            else None
        )

        previous_date = next(
            (
                getattr(match, "date", None)
                for _performance, match in rows[1:]
                if (
                    getattr(match, "date", None)
                    is not None
                    and latest_date is not None
                    and getattr(match, "date", None)
                    < latest_date
                )
            ),
            None,
        )

        days_since = (
            (latest_date - previous_date).days
            if (
                latest_date is not None
                and previous_date is not None
            )
            else None
        )

        return FatigueContext(
            latest_observed_at=(
                latest_observed.isoformat()
                if isinstance(latest_observed, datetime)
                else None
            ),
            matches_on_latest_day=len(same_day),
            legs_on_latest_day=sum(
                (item.legs_won or 0)
                + (item.legs_lost or 0)
                for item in same_day
            ),
            hours_since_previous_match=hours_since,
            days_since_previous_match=days_since,
        )

    @staticmethod
    def _average(values) -> Optional[float]:
        available = [
            float(value)
            for value in values
            if value is not None
        ]
        if not available:
            return None
        return round(sum(available) / len(available), 3)

    @staticmethod
    def _per_match(values, matches: int) -> Optional[float]:
        if matches == 0:
            return None
        return round(
            sum(int(value or 0) for value in values)
            / matches,
            3,
        )

    @staticmethod
    def _per_leg(values, legs: int) -> Optional[float]:
        if legs == 0:
            return None
        return round(
            sum(int(value or 0) for value in values)
            / legs,
            3,
        )

    @staticmethod
    def _percentage_or_none(
        numerator: int,
        denominator: int,
    ) -> Optional[float]:
        if denominator == 0:
            return None
        return round(
            numerator / denominator * 100,
            3,
        )
