from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.player import Player
from app.services.player_feature_engine import (
    PlayerFeatureEngine,
    PlayerFeatureProfile,
)


@dataclass(frozen=True)
class PlayerRatingProfile:
    player_id: int
    player_name: str

    overall_rating: float
    scoring_rating: float
    finishing_rating: float
    maximums_rating: float
    form_rating: float

    momentum_score: Optional[float]
    confidence_score: float

    matches_available: int
    latest_match_id: Optional[int]
    latest_match_date: Optional[str]


class PlayerRatingEngine:
    """
    Build a read-only multi-dimensional player rating profile.

    Ratings are deliberately derived from immutable match data and the
    PlayerFeatureEngine. This service does not update Player.elo or any
    warehouse table, so it is safe to use during historical imports.
    """

    BASE_RATING = 1500.0
    MIN_RATING = 1000.0
    MAX_RATING = 2200.0

    def __init__(
        self,
        *,
        feature_engine: Optional[PlayerFeatureEngine] = None,
    ) -> None:
        self.feature_engine = (
            feature_engine or PlayerFeatureEngine()
        )

    def build_player_rating(
        self,
        db: Session,
        player_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> PlayerRatingProfile:
        player = (
            db.query(Player)
            .filter(Player.id == player_id)
            .first()
        )

        if player is None:
            raise ValueError(
                f"Player {player_id} was not found."
            )

        features = self.feature_engine.build_player_profile(
            db,
            player_id,
            competition_code=competition_code,
        )

        window_5 = features.windows[5]
        window_10 = features.windows[10]
        window_20 = features.windows[20]

        overall = self._overall_rating(
            window_5=window_5,
            window_10=window_10,
            window_20=window_20,
            confidence=features.confidence_score,
        )

        scoring = self._component_rating(
            current=window_5.scoring_power,
            medium=window_10.scoring_power,
            long=window_20.scoring_power,
            confidence=features.confidence_score,
        )

        finishing = self._component_rating(
            current=window_5.finishing_power,
            medium=window_10.finishing_power,
            long=window_20.finishing_power,
            confidence=features.confidence_score,
        )

        maximums = self._maximums_rating(
            current=window_5.scores_180_per_match,
            medium=window_10.scores_180_per_match,
            long=window_20.scores_180_per_match,
            confidence=features.confidence_score,
        )

        form = self._form_rating(
            features=features,
        )

        return PlayerRatingProfile(
            player_id=player.id,
            player_name=player.name,
            overall_rating=overall,
            scoring_rating=scoring,
            finishing_rating=finishing,
            maximums_rating=maximums,
            form_rating=form,
            momentum_score=features.momentum_score,
            confidence_score=features.confidence_score,
            matches_available=features.matches_available,
            latest_match_id=features.latest_match_id,
            latest_match_date=features.latest_match_date,
        )

    def compare_players(
        self,
        db: Session,
        player_a_id: int,
        player_b_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> dict:
        player_a = self.build_player_rating(
            db,
            player_a_id,
            competition_code=competition_code,
        )
        player_b = self.build_player_rating(
            db,
            player_b_id,
            competition_code=competition_code,
        )

        return {
            "player_a": player_a,
            "player_b": player_b,
            "edges": {
                "overall": round(
                    player_a.overall_rating
                    - player_b.overall_rating,
                    3,
                ),
                "scoring": round(
                    player_a.scoring_rating
                    - player_b.scoring_rating,
                    3,
                ),
                "finishing": round(
                    player_a.finishing_rating
                    - player_b.finishing_rating,
                    3,
                ),
                "maximums": round(
                    player_a.maximums_rating
                    - player_b.maximums_rating,
                    3,
                ),
                "form": round(
                    player_a.form_rating
                    - player_b.form_rating,
                    3,
                ),
                "confidence": round(
                    player_a.confidence_score
                    - player_b.confidence_score,
                    3,
                ),
            },
        }

    def _overall_rating(
        self,
        *,
        window_5,
        window_10,
        window_20,
        confidence: float,
    ) -> float:
        win_component = self._weighted_metric(
            window_5.win_percentage,
            window_10.win_percentage,
            window_20.win_percentage,
        )
        leg_component = self._weighted_leg_score(
            window_5,
            window_10,
            window_20,
        )
        scoring_component = self._weighted_metric(
            window_5.scoring_power,
            window_10.scoring_power,
            window_20.scoring_power,
        )
        finishing_component = self._weighted_metric(
            window_5.finishing_power,
            window_10.finishing_power,
            window_20.finishing_power,
        )

        composite = (
            win_component * 0.45
            + leg_component * 0.20
            + scoring_component * 0.20
            + finishing_component * 0.15
        )

        return self._to_rating(
            composite,
            confidence=confidence,
        )

    def _component_rating(
        self,
        *,
        current: Optional[float],
        medium: Optional[float],
        long: Optional[float],
        confidence: float,
    ) -> float:
        score = self._weighted_metric(
            current,
            medium,
            long,
        )

        return self._to_rating(
            score,
            confidence=confidence,
        )

    def _maximums_rating(
        self,
        *,
        current: Optional[float],
        medium: Optional[float],
        long: Optional[float],
        confidence: float,
    ) -> float:
        rate = self._weighted_metric(
            self._normalise_180_rate(current),
            self._normalise_180_rate(medium),
            self._normalise_180_rate(long),
        )

        return self._to_rating(
            rate,
            confidence=confidence,
        )

    def _form_rating(
        self,
        *,
        features: PlayerFeatureProfile,
    ) -> float:
        window_5 = features.windows[5]
        momentum = (
            features.momentum_score
            if features.momentum_score is not None
            else 50.0
        )
        consistency = (
            window_5.average_consistency
            if window_5.average_consistency is not None
            else 50.0
        )

        score = (
            window_5.win_percentage * 0.45
            + momentum * 0.35
            + consistency * 0.20
        )

        return self._to_rating(
            score,
            confidence=features.confidence_score,
        )

    @staticmethod
    def _weighted_metric(
        current: Optional[float],
        medium: Optional[float],
        long: Optional[float],
    ) -> float:
        values = (
            (current, 0.50),
            (medium, 0.30),
            (long, 0.20),
        )

        available = [
            (float(value), weight)
            for value, weight in values
            if value is not None
        ]

        if not available:
            return 50.0

        total_weight = sum(
            weight
            for _value, weight in available
        )

        return sum(
            value * weight
            for value, weight in available
        ) / total_weight

    @staticmethod
    def _weighted_leg_score(
        window_5,
        window_10,
        window_20,
    ) -> float:
        def score(window) -> Optional[float]:
            total_legs = (
                window.legs_won
                + window.legs_lost
            )

            if total_legs == 0:
                return None

            return (
                window.legs_won
                / total_legs
                * 100
            )

        return PlayerRatingEngine._weighted_metric(
            score(window_5),
            score(window_10),
            score(window_20),
        )

    @staticmethod
    def _normalise_180_rate(
        value: Optional[float],
    ) -> Optional[float]:
        if value is None:
            return None

        return min(
            max(value / 3.0 * 100, 0.0),
            100.0,
        )

    def _to_rating(
        self,
        score: float,
        *,
        confidence: float,
    ) -> float:
        bounded_score = min(
            max(score, 0.0),
            100.0,
        )

        raw = (
            self.BASE_RATING
            + (bounded_score - 50.0) * 8.0
        )

        confidence_weight = min(
            max(confidence / 100.0, 0.0),
            1.0,
        )

        adjusted = (
            self.BASE_RATING
            + (
                raw - self.BASE_RATING
            )
            * confidence_weight
        )

        return round(
            min(
                max(adjusted, self.MIN_RATING),
                self.MAX_RATING,
            ),
            3,
        )
