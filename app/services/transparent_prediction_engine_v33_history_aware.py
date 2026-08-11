from __future__ import annotations

from dataclasses import replace
from typing import Optional

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class TransparentPredictionEngineV33HistoryAware:
    """
    Read-only transparent-v3.3 challenger.

    recent_win_rate is scaled only when minimum pre-match
    history is below the configured threshold.

    All other v3.3 behaviour remains unchanged.
    """

    MODEL_VERSION = (
        "transparent-v3.3-history-aware"
    )

    def __init__(
        self,
        *,
        recent_win_rate_multiplier: float = 0.5,
        history_threshold: int = 3,
        base_engine: Optional[
            TransparentPredictionEngineV33
        ] = None,
    ) -> None:
        multiplier = float(
            recent_win_rate_multiplier
        )

        if multiplier < 0.0:
            raise ValueError(
                "recent_win_rate_multiplier "
                "cannot be negative."
            )

        if history_threshold <= 0:
            raise ValueError(
                "history_threshold must be "
                "greater than zero."
            )

        self.recent_win_rate_multiplier = (
            multiplier
        )

        self.history_threshold = int(
            history_threshold
        )

        self.base_engine = (
            base_engine
            or TransparentPredictionEngineV33()
        )

        self.logistic_strength = (
            self.base_engine.logistic_strength
        )

    def predict(
        self,
        snapshot,
    ):
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

        if (
            minimum_history
            >= self.history_threshold
        ):
            prediction = (
                self.base_engine.predict(
                    snapshot
                )
            )

            return replace(
                prediction,
                model_version=(
                    self.MODEL_VERSION
                ),
            )

        features = tuple(
            replace(
                feature,
                weight=(
                    float(feature.weight)
                    * self.recent_win_rate_multiplier
                ),
            )
            if (
                feature.name
                == "recent_win_rate"
            )
            else feature
            for feature
            in self.base_engine.features
        )

        challenger = (
            TransparentPredictionEngineV33(
                features=features,
                logistic_strength=(
                    self.logistic_strength
                ),
            )
        )

        prediction = challenger.predict(
            snapshot
        )

        return replace(
            prediction,
            model_version=(
                self.MODEL_VERSION
            ),
        )

    @property
    def features(self):
        return self.base_engine.features

    def feature_names(self):
        return self.base_engine.feature_names()
