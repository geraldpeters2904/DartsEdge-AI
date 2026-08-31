from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v35 import (
    TransparentPredictionEngineV35,
)


class TransparentPredictionModelV35Adapter:

    MODEL_VERSION = "transparent-v3.5"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV35
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV35()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
