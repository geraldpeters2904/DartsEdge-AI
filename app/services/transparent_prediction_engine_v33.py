from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional

from app.services.prediction_feature_plugin import (
    PredictionFeature,
)
from app.services.transparent_prediction_engine_v32 import (
    TransparentPredictionEngineV32,
)
from app.services.transparent_v3_features import (
    transparent_v32_features,
)


class TransparentPredictionEngineV33(
    TransparentPredictionEngineV32
):
    """
    Transparent v3.3 experimental challenger.

    Evidence-backed changes:
    - recent_form remains at 0.00;
    - overall_strength is reduced from 0.24 to 0.00;
    - scoring_consistency remains at 0.05.
    """

    MODEL_VERSION = "transparent-v3.3"

    def __init__(
        self,
        *,
        features: Optional[
            Iterable[PredictionFeature]
        ] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        if features is None:
            features = tuple(
                replace(
                    feature,
                    weight=0.0,
                )
                if feature.name
                in {
                    "recent_form",
                    "overall_strength",
                }
                else feature
                for feature
                in transparent_v32_features()
            )

        super().__init__(
            features=features,
            logistic_strength=logistic_strength,
        )
