from __future__ import annotations

from typing import Optional

from app.services.transparent_prediction_engine_v31 import (
    TransparentPredictionEngineV31,
)


class TransparentPredictionModelV31Adapter:
    """Registry-compatible adapter for Transparent v3.1."""

    MODEL_VERSION = "transparent-v3.1"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV31
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV31()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
