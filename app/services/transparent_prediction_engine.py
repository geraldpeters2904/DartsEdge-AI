from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Dict, Optional, Tuple

from app.services.prediction_snapshot_engine import (
    MatchPredictionSnapshot,
)


@dataclass(frozen=True)
class PredictionContribution:
    feature: str
    raw_edge: Optional[float]
    normalised_edge: float
    weight: float
    weighted_score: float


@dataclass(frozen=True)
class MatchWinPrediction:
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


class TransparentPredictionEngine:
    """
    Explainable benchmark model for pre-match win probabilities.

    The engine consumes a MatchPredictionSnapshot and converts weighted,
    normalised feature edges into a logistic win probability. It is entirely
    deterministic and read-only, making it suitable for historical back-tests
    and as a baseline challenger for future machine-learning models.
    """

    MODEL_VERSION = "transparent-v1"

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "overall": 0.30,
        "form": 0.20,
        "scoring": 0.20,
        "finishing": 0.15,
        "maximums": 0.10,
        "momentum": 0.05,
    }

    EDGE_SCALES: Dict[str, float] = {
        "overall": 160.0,
        "form": 160.0,
        "scoring": 160.0,
        "finishing": 160.0,
        "maximums": 160.0,
        "momentum": 50.0,
    }

    def __init__(
        self,
        *,
        weights: Optional[Dict[str, float]] = None,
        logistic_strength: float = 3.2,
    ) -> None:
        selected = dict(
            weights or self.DEFAULT_WEIGHTS
        )

        unknown = set(selected) - set(
            self.DEFAULT_WEIGHTS
        )

        if unknown:
            raise ValueError(
                "Unknown prediction weight(s): "
                + ", ".join(sorted(unknown))
            )

        if any(weight < 0 for weight in selected.values()):
            raise ValueError(
                "Prediction weights cannot be negative."
            )

        total = sum(selected.values())

        if total <= 0:
            raise ValueError(
                "Prediction weights must sum to more than zero."
            )

        self.weights = {
            feature: selected.get(feature, 0.0) / total
            for feature in self.DEFAULT_WEIGHTS
        }
        self.logistic_strength = float(
            logistic_strength
        )

        if self.logistic_strength <= 0:
            raise ValueError(
                "logistic_strength must be greater than zero."
            )

    def predict(
        self,
        snapshot: MatchPredictionSnapshot,
    ) -> MatchWinPrediction:
        raw_edges = {
            "overall": snapshot.overall_edge,
            "form": snapshot.form_edge,
            "scoring": snapshot.scoring_edge,
            "finishing": snapshot.finishing_edge,
            "maximums": snapshot.maximums_edge,
            "momentum": snapshot.momentum_edge,
        }

        contributions = tuple(
            self._build_contribution(
                feature,
                raw_edges[feature],
            )
            for feature in self.DEFAULT_WEIGHTS
        )

        model_score = round(
            sum(
                item.weighted_score
                for item in contributions
            ),
            6,
        )

        player_a_probability = self._logistic(
            model_score
        )
        player_b_probability = round(
            100.0 - player_a_probability,
            3,
        )

        winner = (
            snapshot.player_a.player_name
            if player_a_probability >= 50.0
            else snapshot.player_b.player_name
        )

        confidence = self._prediction_confidence(
            snapshot=snapshot,
            player_a_probability=player_a_probability,
        )

        return MatchWinPrediction(
            match_id=snapshot.match_id,
            player_a_name=snapshot.player_a.player_name,
            player_b_name=snapshot.player_b.player_name,
            player_a_probability=player_a_probability,
            player_b_probability=player_b_probability,
            predicted_winner=winner,
            confidence=confidence,
            model_score=model_score,
            model_version=self.MODEL_VERSION,
            contributions=contributions,
            explanation=self._explain(
                snapshot=snapshot,
                contributions=contributions,
                player_a_probability=player_a_probability,
            ),
        )

    def _build_contribution(
        self,
        feature: str,
        raw_edge: Optional[float],
    ) -> PredictionContribution:
        scale = self.EDGE_SCALES[feature]
        normalised = (
            0.0
            if raw_edge is None
            else min(
                max(float(raw_edge) / scale, -1.0),
                1.0,
            )
        )
        weight = self.weights[feature]
        weighted = normalised * weight

        return PredictionContribution(
            feature=feature,
            raw_edge=raw_edge,
            normalised_edge=round(
                normalised,
                6,
            ),
            weight=round(weight, 6),
            weighted_score=round(
                weighted,
                6,
            ),
        )

    def _logistic(
        self,
        model_score: float,
    ) -> float:
        probability = (
            1.0
            / (
                1.0
                + exp(
                    -self.logistic_strength
                    * model_score
                )
            )
        )

        return round(
            probability * 100.0,
            3,
        )

    @staticmethod
    def _prediction_confidence(
        *,
        snapshot: MatchPredictionSnapshot,
        player_a_probability: float,
    ) -> float:
        data_confidence = (
            snapshot.player_a.confidence_score
            + snapshot.player_b.confidence_score
        ) / 2.0

        separation = (
            abs(player_a_probability - 50.0)
            / 50.0
            * 100.0
        )

        confidence = (
            data_confidence * 0.70
            + separation * 0.30
        )

        return round(
            min(
                max(confidence, 0.0),
                100.0,
            ),
            3,
        )

    @staticmethod
    def _explain(
        *,
        snapshot: MatchPredictionSnapshot,
        contributions: Tuple[
            PredictionContribution,
            ...,
        ],
        player_a_probability: float,
    ) -> Tuple[str, ...]:
        ordered = sorted(
            contributions,
            key=lambda item: abs(
                item.weighted_score
            ),
            reverse=True,
        )

        explanations = []

        for contribution in ordered[:3]:
            if abs(
                contribution.weighted_score
            ) < 0.01:
                continue

            favoured = (
                snapshot.player_a.player_name
                if contribution.weighted_score > 0
                else snapshot.player_b.player_name
            )

            explanations.append(
                f"{favoured} holds the stronger "
                f"{contribution.feature} edge."
            )

        if not explanations:
            explanations.append(
                "The model sees very little separation "
                "between the players."
            )

        if (
            snapshot.player_a.confidence_score < 50
            or snapshot.player_b.confidence_score < 50
        ):
            explanations.append(
                "Confidence is reduced because at least "
                "one player has a limited historical sample."
            )

        favoured = (
            snapshot.player_a.player_name
            if player_a_probability >= 50.0
            else snapshot.player_b.player_name
        )

        explanations.append(
            f"{favoured} is the model favourite at "
            f"{max(player_a_probability, 100.0 - player_a_probability):.1f}%."
        )

        return tuple(explanations)
