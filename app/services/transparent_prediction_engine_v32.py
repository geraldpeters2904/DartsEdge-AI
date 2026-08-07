from __future__ import annotations

from typing import Iterable, Optional

from app.services.prediction_feature_plugin import (
    PredictionFeature,
)
from app.services.transparent_prediction_engine_v3 import (
    TransparentPredictionEngineV3,
)
from app.services.transparent_v3_features import (
    transparent_v32_features,
)


class TransparentPredictionEngineV32(
    TransparentPredictionEngineV3
):
    """
    Transparent v3.2 experimental challenger.

    Changes from v3.1:
    - recent_form remains weighted at 0.00;
    - adds recent scoring consistency at weight 0.05.
    """

    MODEL_VERSION = "transparent-v3.2"

    def __init__(
        self,
        *,
        features: Optional[
            Iterable[PredictionFeature]
        ] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        super().__init__(
            features=(
                features
                if features is not None
                else transparent_v32_features()
            ),
            logistic_strength=logistic_strength,
        )
