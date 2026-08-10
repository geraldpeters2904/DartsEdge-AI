from __future__ import annotations

from dataclasses import replace
from typing import Optional

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class TransparentPredictionEngineV33LowHistoryCalibrated:
    """
    Experimental probability-calibration wrapper around
    transparent-v3.3.

    The underlying v3.3 model remains unchanged.

    When:
    - favourite probability is within the configured band; and
    - either player has fewer than the configured number of
      pre-match historical performances;

    the favourite probability is shrunk toward 50%.

    The predicted winner, feature contributions and raw model score
    are preserved.
    """

    BASE_MODEL_VERSION = "transparent-v3.3"

    def __init__(
        self,
        *,
        shrink_fraction: float,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        minimum_history_upper: int = 10,
        base_engine: Optional[
            TransparentPredictionEngineV33
        ] = None,
    ) -> None:
        shrink = float(shrink_fraction)

        if shrink < 0.0 or shrink > 1.0:
            raise ValueError(
                "shrink_fraction must be between 0 and 1."
            )

        if probability_lower < 50.0:
            raise ValueError(
                "probability_lower cannot be below 50."
            )

        if probability_upper <= probability_lower:
            raise ValueError(
                "probability_upper must exceed probability_lower."
            )

        if probability_upper > 100.0:
            raise ValueError(
                "probability_upper cannot exceed 100."
            )

        if minimum_history_upper <= 0:
            raise ValueError(
                "minimum_history_upper must be greater than zero."
            )

        self.shrink_fraction = shrink
        self.probability_lower = float(
            probability_lower
        )
        self.probability_upper = float(
            probability_upper
        )
        self.minimum_history_upper = int(
            minimum_history_upper
        )

        self.base_engine = (
            base_engine
            or TransparentPredictionEngineV33()
        )

        self.MODEL_VERSION = (
            "transparent-v3.3-low-history-calibrated-"
            + self._fraction_label(shrink)
        )

    def predict(self, snapshot):
        prediction = self.base_engine.predict(
            snapshot
        )

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

        favourite_probability = max(
            float(
                prediction.player_a_probability
            ),
            float(
                prediction.player_b_probability
            ),
        )

        target_probability = (
            favourite_probability
            >= self.probability_lower
            and favourite_probability
            < self.probability_upper
        )

        target_history = (
            minimum_history
            < self.minimum_history_upper
        )

        if not (
            target_probability
            and target_history
            and self.shrink_fraction > 0.0
        ):
            return replace(
                prediction,
                model_version=self.MODEL_VERSION,
            )

        calibrated_favourite = (
            50.0
            + (
                favourite_probability
                - 50.0
            )
            * (
                1.0
                - self.shrink_fraction
            )
        )

        if (
            prediction.player_a_probability
            >= prediction.player_b_probability
        ):
            probability_a = (
                calibrated_favourite
            )
            probability_b = (
                100.0
                - calibrated_favourite
            )
        else:
            probability_b = (
                calibrated_favourite
            )
            probability_a = (
                100.0
                - calibrated_favourite
            )

        return replace(
            prediction,
            player_a_probability=round(
                probability_a,
                3,
            ),
            player_b_probability=round(
                probability_b,
                3,
            ),
            model_version=self.MODEL_VERSION,
        )

    @staticmethod
    def _fraction_label(
        shrink_fraction: float,
    ) -> str:
        percentage = int(
            round(
                float(shrink_fraction)
                * 100.0
            )
        )

        return (
            f"shrink-{percentage:02d}"
        )
