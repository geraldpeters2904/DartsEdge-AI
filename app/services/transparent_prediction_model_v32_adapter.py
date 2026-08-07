from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v32 import (
    TransparentPredictionEngineV32,
)


class TransparentPredictionModelV32Adapter:
    MODEL_VERSION = "transparent-v3.2"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV32
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV32()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
