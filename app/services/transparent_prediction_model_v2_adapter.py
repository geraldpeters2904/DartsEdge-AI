from __future__ import annotations

from typing import Optional

from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.transparent_prediction_engine_v2 import (
    TransparentPredictionEngineV2,
)


class TransparentPredictionModelV2Adapter:
    """
    Registry-compatible wrapper for Transparent v2.

    PredictionValidationEngine asks a snapshot engine for one historical
    snapshot, then passes it to the model's predict method. This adapter simply
    exposes the same model interface as v1.
    """

    MODEL_VERSION = "transparent-v2"

    def __init__(
        self,
        *,
        engine: Optional[
            TransparentPredictionEngineV2
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or TransparentPredictionEngineV2()
        )

    def predict(self, snapshot):
        return self.engine.predict(snapshot)
