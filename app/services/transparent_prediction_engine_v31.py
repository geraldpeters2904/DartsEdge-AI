from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional

from app.services.prediction_feature_plugin import (
    PredictionFeature,
)
from app.services.transparent_prediction_engine_v3 import (
    TransparentPredictionEngineV3,
)
from app.services.transparent_v3_features import (
    default_transparent_v3_features,
)


class TransparentPredictionEngineV31(
    TransparentPredictionEngineV3
):
    """
    Transparent v3.1 challenger.

    Evidence-backed change from v3:
    recent_form weight is reduced from 0.18 to 0.00.

    The feature remains installed so it can be redesigned or
    re-enabled in future experiments.
    """

    MODEL_VERSION = "transparent-v3.1"

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
                if feature.name == "recent_form"
                else feature
                for feature in (
                    default_transparent_v3_features()
                )
            )

        super().__init__(
            features=features,
            logistic_strength=logistic_strength,
        )
