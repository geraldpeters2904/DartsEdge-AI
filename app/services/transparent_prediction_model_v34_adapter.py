from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v34 import (
    TransparentPredictionEngineV34,
)


class TransparentPredictionModelV34Adapter:

    MODEL_VERSION = "transparent-v3.4"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV34
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV34()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
