from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Protocol

from app.services.transparent_prediction_engine import (
    TransparentPredictionEngine,
)
from app.services.transparent_prediction_model_v2_adapter import (
    TransparentPredictionModelV2Adapter,
)
from app.services.transparent_prediction_model_v3_adapter import (
    TransparentPredictionModelV3Adapter,
)
from app.services.transparent_prediction_model_v31_adapter import (
    TransparentPredictionModelV31Adapter,
)
from app.services.transparent_prediction_model_v32_adapter import (
    TransparentPredictionModelV32Adapter,
)
from app.services.transparent_prediction_model_v33_adapter import (
    TransparentPredictionModelV33Adapter,
)


class PredictionModel(Protocol):
    MODEL_VERSION: str

    def predict(self, snapshot):
        ...


@dataclass(frozen=True)
class RegisteredPredictionModel:
    name: str
    version: str
    model: PredictionModel


class PredictionModelRegistry:
    """
    Resolve prediction models by stable name or version.

    The registry keeps model selection out of dashboards and services, making
    it possible to add challenger models later without changing callers.
    """

    def __init__(
        self,
        *,
        models: Iterable[tuple[str, PredictionModel]] | None = None,
        default_model: str = "transparent",
    ) -> None:
        self._models: Dict[str, RegisteredPredictionModel] = {}

        selected_models = (
            list(models)
            if models is not None
            else [
                (
                    "transparent",
                    TransparentPredictionEngine(),
                ),
                (
                    "transparent-v2",
                    TransparentPredictionModelV2Adapter(),
                ),
                (
                    "transparent-v3",
                    TransparentPredictionModelV3Adapter(),
                ),
                (
                    "transparent-v3.1",
                    TransparentPredictionModelV31Adapter(),
                ),
                (
                    "transparent-v3.2",
                    TransparentPredictionModelV32Adapter(),
                ),
                (
                    "transparent-v3.3",
                    TransparentPredictionModelV33Adapter(),
                ),
            ]
        )

        for name, model in selected_models:
            self.register(name, model)

        self.set_default(default_model)

    def register(
        self,
        name: str,
        model: PredictionModel,
    ) -> None:
        key = self._normalise(name)

        if not key:
            raise ValueError(
                "Prediction model name is required."
            )

        version = str(
            getattr(model, "MODEL_VERSION", "")
            or ""
        ).strip()

        if not version:
            raise ValueError(
                "Prediction model must expose MODEL_VERSION."
            )

        self._models[key] = RegisteredPredictionModel(
            name=key,
            version=version,
            model=model,
        )

    def get(
        self,
        name: str | None = None,
    ) -> PredictionModel:
        key = (
            self._default_model
            if name is None
            else self._normalise(name)
        )

        if key not in self._models:
            available = ", ".join(
                sorted(self._models)
            )
            raise ValueError(
                f"Unknown prediction model: {name!r}. "
                f"Available models: {available or 'none'}."
            )

        return self._models[key].model

    def get_registered(
        self,
        name: str | None = None,
    ) -> RegisteredPredictionModel:
        key = (
            self._default_model
            if name is None
            else self._normalise(name)
        )

        if key not in self._models:
            self.get(key)

        return self._models[key]

    def set_default(
        self,
        name: str,
    ) -> None:
        key = self._normalise(name)

        if key not in self._models:
            available = ", ".join(
                sorted(self._models)
            )
            raise ValueError(
                f"Default model {name!r} is not registered. "
                f"Available models: {available or 'none'}."
            )

        self._default_model = key

    @property
    def default_name(self) -> str:
        return self._default_model

    def names(self) -> list[str]:
        return sorted(self._models)

    def versions(self) -> dict[str, str]:
        return {
            name: registered.version
            for name, registered in sorted(
                self._models.items()
            )
        }

    @staticmethod
    def _normalise(
        value: str,
    ) -> str:
        return str(value or "").strip().casefold()


prediction_model_registry = PredictionModelRegistry()
