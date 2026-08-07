from __future__ import annotations

from dataclasses import dataclass, replace
from math import exp
from typing import Iterable, Optional, Tuple

from app.services.prediction_feature_plugin import (
    FeatureContribution,
    PredictionFeature,
)
from app.services.transparent_v3_features import (
    default_transparent_v3_features,
)


@dataclass(frozen=True)
class TransparentV3Prediction:
    match_id: int
    player_a_name: str
    player_b_name: str
    player_a_probability: float
    player_b_probability: float
    predicted_winner: str
    confidence: float
    model_score: float
    model_version: str
    contributions: Tuple[FeatureContribution, ...]
    explanation: Tuple[str, ...]


class TransparentPredictionEngineV3:
    MODEL_VERSION = "transparent-v3"

    def __init__(
        self,
        *,
        features: Optional[Iterable[PredictionFeature]] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        self.features = tuple(
            features if features is not None
            else default_transparent_v3_features()
        )
        if not self.features:
            raise ValueError("At least one prediction feature is required.")

        names = [feature.name for feature in self.features]
        if len(names) != len(set(names)):
            raise ValueError("Prediction feature names must be unique.")

        self.logistic_strength = float(logistic_strength)
        if self.logistic_strength <= 0:
            raise ValueError("logistic_strength must be greater than zero.")

    def predict(self, snapshot) -> TransparentV3Prediction:
        contributions = tuple(
            feature.score(snapshot)
            for feature in self.features
        )
        model_score = round(
            sum(item.weighted_score for item in contributions),
            6,
        )
        probability_a = round(
            100.0 / (
                1.0 + exp(-self.logistic_strength * model_score)
            ),
            3,
        )
        probability_b = round(100.0 - probability_a, 3)
        winner = (
            snapshot.player_a.player_name
            if probability_a >= 50.0
            else snapshot.player_b.player_name
        )

        data_confidence = (
            snapshot.player_a.confidence_score
            + snapshot.player_b.confidence_score
        ) / 2.0
        separation = abs(probability_a - 50.0) / 50.0 * 100.0
        confidence = round(
            min(max(data_confidence * 0.70 + separation * 0.30, 0.0), 100.0),
            3,
        )

        ordered = sorted(
            contributions,
            key=lambda item: abs(item.weighted_score),
            reverse=True,
        )
        explanation = tuple(
            item.explanation
            for item in ordered[:4]
            if abs(item.weighted_score) >= 0.005
        ) or ("The feature plugins see very little separation.",)

        return TransparentV3Prediction(
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
            explanation=explanation,
        )

    def without_features(self, *feature_names: str):
        disabled = {str(name).strip() for name in feature_names}
        return TransparentPredictionEngineV3(
            features=(
                feature for feature in self.features
                if feature.name not in disabled
            ),
            logistic_strength=self.logistic_strength,
        )

    def with_feature_weight(self, feature_name: str, weight: float):
        if weight < 0:
            raise ValueError("Feature weight cannot be negative.")

        found = False
        updated = []
        for feature in self.features:
            if feature.name == feature_name:
                updated.append(replace(feature, weight=float(weight)))
                found = True
            else:
                updated.append(feature)

        if not found:
            raise ValueError(f"Unknown prediction feature: {feature_name}.")

        return TransparentPredictionEngineV3(
            features=updated,
            logistic_strength=self.logistic_strength,
        )

    def feature_names(self) -> list[str]:
        return [feature.name for feature in self.features]
