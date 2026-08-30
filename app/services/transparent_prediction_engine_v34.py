from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Optional

from app.services.prediction_feature_plugin import (
    PredictionFeature,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class TransparentPredictionEngineV34(
    TransparentPredictionEngineV33
):
    """
    Transparent v3.4 experimental challenger.

    Evidence-backed changes from v3.3:

    - finishing_strength reduced from 0.12 to 0.08;
    - maximums_strength reduced from 0.08 to 0.00.

    All other v3.3 feature weights and prediction mechanics
    remain unchanged.
    """

    MODEL_VERSION = "transparent-v3.4"

    def __init__(
        self,
        *,
        features: Optional[
            Iterable[PredictionFeature]
        ] = None,
        logistic_strength: float = 3.0,
    ) -> None:
        if features is None:
            baseline = TransparentPredictionEngineV33()

            features = tuple(
                replace(
                    feature,
                    weight={
                        "finishing_strength": 0.08,
                        "maximums_strength": 0.00,
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
