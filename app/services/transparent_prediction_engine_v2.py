from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Dict, Optional, Tuple

from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureProfile,
)
from app.services.transparent_prediction_engine import (
    PredictionContribution,
)


@dataclass(frozen=True)
class AdvancedPlayerPredictionInput:
    player_id: int
    player_name: str
    overall_rating: float
    scoring_rating: float
    finishing_rating: float
    maximums_rating: float
    form_rating: float
    confidence_score: float
    advanced_features: AdvancedPlayerFeatureProfile


@dataclass(frozen=True)
class AdvancedMatchPredictionInput:
    match_id: int
    player_a: AdvancedPlayerPredictionInput
    player_b: AdvancedPlayerPredictionInput


@dataclass(frozen=True)
class AdvancedMatchWinPrediction:
    match_id: int
    player_a_name: str
    player_b_name: str
    player_a_probability: float
    player_b_probability: float
    predicted_winner: str
    confidence: float
    model_score: float
    model_version: str
    contributions: Tuple[PredictionContribution, ...]
    explanation: Tuple[str, ...]


class TransparentPredictionEngineV2:
    """
    Explainable challenger model using validated advanced features.

    Throw-order and intraday fatigue are intentionally excluded because the
    historical warehouse does not currently populate reliable source values.
    """

    MODEL_VERSION = "transparent-v2"

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "overall": 0.20,
        "form": 0.15,
        "scoring": 0.12,
        "finishing": 0.10,
        "maximums": 0.06,
        "recent_win_rate": 0.10,
        "average_trend": 0.08,
        "checkout_trend": 0.07,
        "maximums_trend": 0.05,
        "deciding_strength": 0.04,
        "per_leg_scoring": 0.03,
    }

    EDGE_SCALES: Dict[str, float] = {
        "overall": 160.0,
        "form": 160.0,
        "scoring": 160.0,
        "finishing": 160.0,
        "maximums": 160.0,
        "recent_win_rate": 50.0,
        "average_trend": 8.0,
        "checkout_trend": 20.0,
        "maximums_trend": 1.5,
        "deciding_strength": 50.0,
        "per_leg_scoring": 0.25,
    }

    def __init__(
        self,
        *,
        weights: Optional[Dict[str, float]] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        selected = dict(weights or self.DEFAULT_WEIGHTS)
        unknown = set(selected) - set(self.DEFAULT_WEIGHTS)

        if unknown:
            raise ValueError(
                "Unknown prediction weight(s): "
                + ", ".join(sorted(unknown))
            )

        if any(value < 0 for value in selected.values()):
            raise ValueError(
                "Prediction weights cannot be negative."
            )

        total = sum(selected.values())

        if total <= 0:
            raise ValueError(
                "Prediction weights must sum to more than zero."
            )

        self.weights = {
            name: selected.get(name, 0.0) / total
            for name in self.DEFAULT_WEIGHTS
        }
        self.logistic_strength = float(logistic_strength)

        if self.logistic_strength <= 0:
            raise ValueError(
                "logistic_strength must be greater than zero."
            )

    def predict(
        self,
        snapshot: AdvancedMatchPredictionInput,
    ) -> AdvancedMatchWinPrediction:
        raw_edges = self._raw_edges(snapshot)

        contributions = tuple(
            self._contribution(name, raw_edges[name])
            for name in self.DEFAULT_WEIGHTS
        )

        model_score = round(
            sum(item.weighted_score for item in contributions),
            6,
        )

        probability_a = self._logistic(model_score)
        probability_b = round(100.0 - probability_a, 3)

        winner = (
            snapshot.player_a.player_name
            if probability_a >= 50.0
            else snapshot.player_b.player_name
        )

        confidence = self._confidence(
            snapshot,
            probability_a,
        )

        return AdvancedMatchWinPrediction(
            match_id=snapshot.match_id,
            player_a_name=snapshot.player_a.player_name,
            player_b_name=snapshot.player_b.player_name,
            player_a_probability=probability_a,
            player_b_probability=probability_b,
            predicted_winner=winner,
            confidence=confidence,
            model_score=model_score,
            model_version=self.MODEL_VERSION,
            contributions=contributions,
            explanation=self._explain(
                snapshot,
                contributions,
                probability_a,
            ),
        )

    def _raw_edges(
        self,
        snapshot: AdvancedMatchPredictionInput,
    ) -> Dict[str, Optional[float]]:
        a = snapshot.player_a
        b = snapshot.player_b

        return {
            "overall": a.overall_rating - b.overall_rating,
            "form": a.form_rating - b.form_rating,
            "scoring": a.scoring_rating - b.scoring_rating,
            "finishing": a.finishing_rating - b.finishing_rating,
            "maximums": a.maximums_rating - b.maximums_rating,
            "recent_win_rate": (
                self._window_value(a, "last_5", "win_percentage")
                - self._window_value(b, "last_5", "win_percentage")
            ),
            "average_trend": (
                self._trend_value(a, "three_dart_average")
                - self._trend_value(b, "three_dart_average")
            ),
            "checkout_trend": (
                self._trend_value(a, "checkout_percentage")
                - self._trend_value(b, "checkout_percentage")
            ),
            "maximums_trend": (
                self._trend_value(a, "scores_180_per_match")
                - self._trend_value(b, "scores_180_per_match")
            ),
            "deciding_strength": (
                self._window_value(
                    a,
                    "last_20",
                    "deciding_win_percentage",
                    default=50.0,
                )
                - self._window_value(
                    b,
                    "last_20",
                    "deciding_win_percentage",
                    default=50.0,
                )
            ),
            "per_leg_scoring": (
                self._per_leg_score(a)
                - self._per_leg_score(b)
            ),
        }

    @staticmethod
    def _window_value(
        player,
        window_name: str,
        field_name: str,
        *,
        default: float = 0.0,
    ) -> float:
        window = player.advanced_features.windows[window_name]
        value = getattr(window, field_name)
        return float(value) if value is not None else default

    @staticmethod
    def _trend_value(
        player,
        metric: str,
    ) -> float:
        for trend in player.advanced_features.trends:
            if trend.metric == metric:
                return float(trend.absolute_change or 0.0)
        return 0.0

    @staticmethod
    def _per_leg_score(player) -> float:
        window = player.advanced_features.windows["last_20"]
        return (
            float(window.scores_140_plus_per_leg or 0.0) * 0.55
            + float(window.scores_180_per_leg or 0.0) * 0.45
        )

    def _contribution(
        self,
        feature: str,
        raw_edge: Optional[float],
    ) -> PredictionContribution:
        normalised = (
            0.0
            if raw_edge is None
            else min(
                max(
                    float(raw_edge) / self.EDGE_SCALES[feature],
                    -1.0,
                ),
                1.0,
            )
        )
        weight = self.weights[feature]
        weighted = normalised * weight

        return PredictionContribution(
            feature=feature,
            raw_edge=raw_edge,
            normalised_edge=round(normalised, 6),
            weight=round(weight, 6),
            weighted_score=round(weighted, 6),
        )

    def _logistic(self, score: float) -> float:
        probability = 1.0 / (
            1.0 + exp(-self.logistic_strength * score)
        )
        return round(probability * 100.0, 3)

    @staticmethod
    def _confidence(
        snapshot: AdvancedMatchPredictionInput,
        probability_a: float,
    ) -> float:
        data_confidence = (
            snapshot.player_a.confidence_score
            + snapshot.player_b.confidence_score
        ) / 2.0
        separation = abs(probability_a - 50.0) / 50.0 * 100.0

        return round(
            min(
                max(
                    data_confidence * 0.75
                    + separation * 0.25,
                    0.0,
                ),
                100.0,
            ),
            3,
        )

    @staticmethod
    def _explain(
        snapshot,
        contributions,
        probability_a,
    ) -> Tuple[str, ...]:
        ordered = sorted(
            contributions,
            key=lambda item: abs(item.weighted_score),
            reverse=True,
        )

        explanation = []

        for item in ordered[:4]:
            if abs(item.weighted_score) < 0.008:
                continue

            favoured = (
                snapshot.player_a.player_name
                if item.weighted_score > 0
                else snapshot.player_b.player_name
            )
            explanation.append(
                f"{favoured} holds the stronger "
                f"{item.feature.replace('_', ' ')} edge."
            )

        if not explanation:
            explanation.append(
                "The advanced model sees very little separation."
            )

        winner = (
            snapshot.player_a.player_name
            if probability_a >= 50.0
            else snapshot.player_b.player_name
        )
        explanation.append(
            f"{winner} is the model favourite at "
            f"{max(probability_a, 100.0 - probability_a):.1f}%."
        )

        return tuple(explanation)
