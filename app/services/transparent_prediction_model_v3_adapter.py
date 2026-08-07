from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v3 import (
    TransparentPredictionEngineV3,
)


class TransparentPredictionModelV3Adapter:
    """Registry-compatible wrapper for Transparent v3."""

    MODEL_VERSION = "transparent-v3"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV3
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV3()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
