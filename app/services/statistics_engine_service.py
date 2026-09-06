from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player_match_performance import PlayerMatchPerformance


@dataclass(frozen=True)
class PlayerStatistics:
    player_id: int
    competition_code: Optional[str]

    matches_played: int
    wins: int
    losses: int
    win_percentage: float

    legs_won: int
    legs_lost: int
    leg_difference: int

    average_three_dart_average: Optional[float]
    average_first_nine_average: Optional[float]

    scores_100_plus: int
    scores_140_plus: int
    scores_180: int
    maximums_per_match: float

    checkout_attempts: int
    checkouts_completed: int
    calculated_checkout_percentage: Optional[float]
    average_reported_checkout_percentage: Optional[float]
    highest_checkout: Optional[int]

    recent_form: List[str]


class StatisticsEngineService:
    """Derive reusable player statistics from immutable match performances."""

    def build_player_statistics(
        self,
        db: Session,
        player_id: int,
        *,
        competition_code: Optional[str] = None,
        recent_limit: int = 10,
    ) -> PlayerStatistics:
        query = (
            db.query(PlayerMatchPerformance, Match)
            .join(
                Match,
                Match.id == PlayerMatchPerformance.match_id,
            )
            .filter(PlayerMatchPerformance.player_id == player_id)
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        rows = query.order_by(
            Match.date.desc(),
            PlayerMatchPerformance.created_at.desc(),
            PlayerMatchPerformance.id.desc(),
        ).all()

        performances = [performance for performance, _match in rows]

        matches_played = len(performances)
        wins = sum(
            1
            for performance in performances
            if performance.won_match is True
        )
        losses = sum(
            1
            for performance in performances
            if performance.won_match is False
        )

        legs_won = sum(
            performance.legs_won or 0
            for performance in performances
        )
        legs_lost = sum(
            performance.legs_lost or 0
            for performance in performances
        )

        scores_100_plus = sum(
            performance.scores_100_plus or 0
            for performance in performances
        )
        scores_140_plus = sum(
            performance.scores_140_plus or 0
            for performance in performances
        )
        scores_180_values = [
            int(performance.scores_180)
            for performance in performances
            if performance.scores_180 is not None
        ]

        scores_180 = sum(scores_180_values)

        checkout_attempts = sum(
            performance.checkout_attempts or 0
            for performance in performances
        )
        checkouts_completed = sum(
            performance.checkouts_completed or 0
            for performance in performances
        )

        highest_checkout_values = [
            performance.highest_checkout
            for performance in performances
            if performance.highest_checkout is not None
        ]

        recent_form = [
            "W" if performance.won_match else "L"
            for performance in performances[:recent_limit]
            if performance.won_match is not None
        ]

        return PlayerStatistics(
            player_id=player_id,
            competition_code=competition_code,
            matches_played=matches_played,
            wins=wins,
            losses=losses,
            win_percentage=self._percentage(
                wins,
                matches_played,
            ),
            legs_won=legs_won,
            legs_lost=legs_lost,
            leg_difference=legs_won - legs_lost,
            average_three_dart_average=self._average(
                performance.three_dart_average
                for performance in performances
            ),
            average_first_nine_average=self._average(
                performance.first_nine_average
                for performance in performances
            ),
            scores_100_plus=scores_100_plus,
            scores_140_plus=scores_140_plus,
            scores_180=scores_180,
            maximums_per_match=(
                round(scores_180 / len(scores_180_values), 3)
                if scores_180_values
                else 0.0
            ),
            checkout_attempts=checkout_attempts,
            checkouts_completed=checkouts_completed,
            calculated_checkout_percentage=(
                self._percentage(
                    checkouts_completed,
                    checkout_attempts,
                )
                if checkout_attempts
                else None
            ),
            average_reported_checkout_percentage=self._average(
                performance.checkout_percentage
                for performance in performances
            ),
            highest_checkout=(
                max(highest_checkout_values)
                if highest_checkout_values
                else None
            ),
            recent_form=recent_form,
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

        return round(
            sum(available) / len(available),
            3,
        )

    @staticmethod
    def _percentage(
        numerator: int,
        denominator: int,
    ) -> float:
        if denominator == 0:
            return 0.0

        return round(
            numerator / denominator * 100,
            3,
        )
