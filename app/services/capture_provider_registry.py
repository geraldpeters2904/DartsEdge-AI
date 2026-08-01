from __future__ import annotations

from typing import Dict

from app.services.capture_provider import CaptureProvider
from app.services.manual_capture_provider import (
    ManualCaptureProvider,
)
from app.services.safari_capture_provider import (
    SafariCaptureProvider,
)


class CaptureProviderRegistry:
    """Resolve capture providers by stable provider name."""

    def __init__(
        self,
        *,
        include_safari: bool = True,
    ) -> None:
        self._providers: Dict[str, CaptureProvider] = {}

        self.register(ManualCaptureProvider())

        if include_safari:
            self.register(SafariCaptureProvider())

    def register(
        self,
        provider: CaptureProvider,
    ) -> None:
        name = str(provider.name or "").strip().casefold()

        if not name:
            raise ValueError(
                "Capture provider must have a name."
            )

        self._providers[name] = provider

    def get(
        self,
        name: str,
    ) -> CaptureProvider:
        key = str(name or "").strip().casefold()

        if key not in self._providers:
            available = ", ".join(
                sorted(self._providers)
            )

            raise ValueError(
                f"Unknown capture provider: {name!r}. "
                f"Available providers: "
                f"{available or 'none'}."
            )

        return self._providers[key]

    def names(self) -> list[str]:
        return sorted(self._providers)


capture_provider_registry = CaptureProviderRegistry()
