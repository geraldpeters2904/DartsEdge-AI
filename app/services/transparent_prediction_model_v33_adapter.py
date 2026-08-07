from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class TransparentPredictionModelV33Adapter:
    MODEL_VERSION = "transparent-v3.3"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV33
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV33()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
