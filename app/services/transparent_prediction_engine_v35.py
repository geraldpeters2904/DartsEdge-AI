from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional

from app.services.prediction_feature_plugin import (
    PredictionFeature,
)
from app.services.transparent_prediction_engine_v34 import (
    TransparentPredictionEngineV34,
)


class TransparentPredictionEngineV35(
    TransparentPredictionEngineV34
):
    """
    Transparent v3.5 experimental challenger.

    Inherits the evidence-backed v3.4 changes:

    - finishing_strength reduced from 0.12 to 0.08;
    - maximums_strength reduced from 0.08 to 0.00.

    Additional evidence-backed changes:

    - recent_win_rate reduced from 0.10 to 0.00;
    - checkout_trend reduced from 0.07 to 0.00.

    The additional changes improved accuracy, Brier score,
    and log loss against both v3.3 and v3.4 across three
    consecutive 3,000-match later out-of-sample windows.

    All other feature weights and prediction mechanics
    remain unchanged. Logistic strength remains 3.0.
    """

    MODEL_VERSION = "transparent-v3.5"

    def __init__(
        self,
        *,
        features: Optional[
            Iterable[PredictionFeature]
        ] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        if features is None:
            baseline = TransparentPredictionEngineV34()

            features = tuple(
                replace(
                    feature,
                    weight={
                        "recent_win_rate": 0.00,
                        "checkout_trend": 0.00,
                    }.get(
                        feature.name,
                        feature.weight,
                    ),
                )
                for feature in baseline.features
            )

        super().__init__(
            features=features,
            logistic_strength=logistic_strength,
        )
