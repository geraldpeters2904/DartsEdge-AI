from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player_match_performance import PlayerMatchPerformance


@dataclass(frozen=True)
class RollingPlayerFeatures:
    window: int
    matches: int
    wins: int
    losses: int
    win_percentage: float
    legs_won: int
    legs_lost: int
    leg_difference: int
    legs_per_match: Optional[float]
    average_three_dart_average: Optional[float]
    average_first_nine_average: Optional[float]
    scores_100_plus_per_match: Optional[float]
    scores_140_plus_per_match: Optional[float]
    scores_180_per_match: Optional[float]
    checkout_attempts: int
    checkouts_completed: int
    calculated_checkout_percentage: Optional[float]
    average_reported_checkout_percentage: Optional[float]
    checkout_data_matches: int
    highest_checkout: Optional[int]
    average_highest_checkout: Optional[float]
    average_consistency: Optional[float]
    scoring_power: Optional[float]
    finishing_power: Optional[float]


@dataclass(frozen=True)
class PlayerFeatureProfile:
    player_id: int
    competition_code: Optional[str]
    matches_available: int
    latest_match_id: Optional[int]
    latest_match_date: Optional[str]
    recent_form: Tuple[str, ...]
    momentum_score: Optional[float]
    confidence_score: float
    windows: Dict[int, RollingPlayerFeatures]


class PlayerFeatureEngine:
    DEFAULT_WINDOWS = (5, 10, 20)

    def build_player_profile(
        self,
        db: Session,
        player_id: int,
        *,
        competition_code: Optional[str] = None,
        windows: Iterable[int] = DEFAULT_WINDOWS,
    ) -> PlayerFeatureProfile:
        ordered_windows = tuple(sorted({int(w) for w in windows if int(w) > 0}))
        if not ordered_windows:
            raise ValueError("At least one positive feature window is required.")

        query = (
            db.query(PlayerMatchPerformance, Match)
            .join(Match, Match.id == PlayerMatchPerformance.match_id)
            .filter(PlayerMatchPerformance.player_id == player_id)
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code == competition_code
            )

        rows = query.order_by(
            Match.date.desc(),
            PlayerMatchPerformance.created_at.desc(),
            PlayerMatchPerformance.id.desc(),
        ).all()

        performances = [performance for performance, _match in rows]
        latest_match = rows[0][1] if rows else None

        return PlayerFeatureProfile(
            player_id=player_id,
            competition_code=competition_code,
            matches_available=len(performances),
            latest_match_id=latest_match.id if latest_match else None,
            latest_match_date=(
                latest_match.date.isoformat()
                if latest_match and latest_match.date
                else None
            ),
            recent_form=tuple(
                "W" if p.won_match else "L"
                for p in performances[:10]
                if p.won_match is not None
            ),
            momentum_score=self._momentum_score(performances[:5]),
            confidence_score=self._confidence_score(performances),
            windows={
                window: self._build_window(performances[:window], window)
                for window in ordered_windows
            },
        )

    def _build_window(self, performances, window: int) -> RollingPlayerFeatures:
        matches = len(performances)
        wins = sum(1 for p in performances if p.won_match is True)
        losses = sum(1 for p in performances if p.won_match is False)
        legs_won = sum(p.legs_won or 0 for p in performances)
        legs_lost = sum(p.legs_lost or 0 for p in performances)

        checkout_rows = [
            p for p in performances
            if p.checkout_attempts is not None
            and p.checkouts_completed is not None
        ]
        checkout_attempts = sum(p.checkout_attempts or 0 for p in checkout_rows)
        checkouts_completed = sum(p.checkouts_completed or 0 for p in checkout_rows)

        average = self._average(p.three_dart_average for p in performances)
        first_nine = self._average(p.first_nine_average for p in performances)
        scores_100 = self._per_match((p.scores_100_plus for p in performances), matches)
        scores_140 = self._per_match((p.scores_140_plus for p in performances), matches)
        scores_180 = self._per_match((p.scores_180 for p in performances), matches)

        checkout_percentage = (
            self._percentage(checkouts_completed, checkout_attempts)
            if checkout_attempts
            else None
        )
        reported_checkout = self._average(
            p.checkout_percentage for p in checkout_rows
        )
        highest_values = [
            p.highest_checkout for p in performances
            if p.highest_checkout is not None
        ]
        highest_checkout = max(highest_values) if highest_values else None

        consistency = self._consistency_score(
            p.three_dart_average for p in performances
        )

        return RollingPlayerFeatures(
            window=window,
            matches=matches,
            wins=wins,
            losses=losses,
            win_percentage=self._percentage(wins, matches),
            legs_won=legs_won,
            legs_lost=legs_lost,
            leg_difference=legs_won - legs_lost,
            legs_per_match=(
                round((legs_won + legs_lost) / matches, 3)
                if matches else None
            ),
            average_three_dart_average=average,
            average_first_nine_average=first_nine,
            scores_100_plus_per_match=scores_100,
            scores_140_plus_per_match=scores_140,
            scores_180_per_match=scores_180,
            checkout_attempts=checkout_attempts,
            checkouts_completed=checkouts_completed,
            calculated_checkout_percentage=checkout_percentage,
            average_reported_checkout_percentage=reported_checkout,
            checkout_data_matches=len(checkout_rows),
            highest_checkout=highest_checkout,
            average_highest_checkout=self._average(highest_values),
            average_consistency=consistency,
            scoring_power=self._scoring_power(
                average,
                scores_140,
                scores_180,
            ),
            finishing_power=self._finishing_power(
                checkout_percentage,
                highest_checkout,
                legs_won,
                matches,
            ),
        )

    @staticmethod
    def _momentum_score(performances) -> Optional[float]:
        weighted = [
            (5 - index, 1.0 if p.won_match else 0.0)
            for index, p in enumerate(performances[:5])
            if p.won_match is not None
        ]
        if not weighted:
            return None
        total_weight = sum(weight for weight, _ in weighted)
        score = sum(weight * result for weight, result in weighted)
        return round(score / total_weight * 100, 3)

    @staticmethod
    def _confidence_score(performances) -> float:
        if not performances:
            return 0.0
        sample_score = min(len(performances) / 20, 1.0) * 60
        values = []
        for p in performances[:20]:
            values.extend([
                p.won_match,
                p.legs_won,
                p.legs_lost,
                p.three_dart_average,
                p.scores_180,
                p.checkout_attempts,
                p.checkouts_completed,
            ])
        completeness = sum(v is not None for v in values) / len(values)
        return round(sample_score + completeness * 40, 3)

    @staticmethod
    def _scoring_power(average, scores_140, scores_180):
        if average is None and scores_140 is None and scores_180 is None:
            return None
        return round(
            (
                min(max((average or 0.0) / 110, 0.0), 1.0) * 0.60
                + min(max((scores_140 or 0.0) / 8, 0.0), 1.0) * 0.25
                + min(max((scores_180 or 0.0) / 3, 0.0), 1.0) * 0.15
            ) * 100,
            3,
        )

    @staticmethod
    def _finishing_power(checkout_percentage, highest_checkout, legs_won, matches):
        if checkout_percentage is None and highest_checkout is None and matches == 0:
            return None
        return round(
            (
                min(max((checkout_percentage or 0.0) / 60, 0.0), 1.0) * 0.60
                + min(max((highest_checkout or 0) / 170, 0.0), 1.0) * 0.20
                + min(max(((legs_won / matches) if matches else 0.0) / 4, 0.0), 1.0) * 0.20
            ) * 100,
            3,
        )

    @staticmethod
    def _consistency_score(values):
        available = [float(v) for v in values if v is not None]
        if not available:
            return None
        if len(available) == 1:
            return 100.0
        return round(max(0.0, 100.0 - pstdev(available) * 5), 3)

    @staticmethod
    def _average(values):
        available = [float(v) for v in values if v is not None]
        if not available:
            return None
        return round(sum(available) / len(available), 3)

    @staticmethod
    def _per_match(values, matches):
        if matches == 0:
            return None
        return round(sum(int(v or 0) for v in values) / matches, 3)

    @staticmethod
    def _percentage(numerator, denominator):
        if denominator == 0:
            return 0.0
        return round(numerator / denominator * 100, 3)
