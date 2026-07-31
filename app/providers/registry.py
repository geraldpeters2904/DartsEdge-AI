from __future__ import annotations

from typing import Dict, Iterable, List

from app.providers.contracts import ProviderAdapter


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: Dict[str, ProviderAdapter] = {}

    def register(self, provider: ProviderAdapter) -> ProviderAdapter:
        if not provider.provider_id or provider.provider_id.strip() != provider.provider_id:
            raise ValueError("provider_id must be a non-empty trimmed string")
        if provider.provider_id in self._providers:
            raise ValueError(f"Provider '{provider.provider_id}' is already registered")
        self._providers[provider.provider_id] = provider
        return provider

    def get(self, provider_id: str) -> ProviderAdapter:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"Unknown provider '{provider_id}'") from exc

    def all(self) -> List[ProviderAdapter]:
        return [self._providers[key] for key in sorted(self._providers)]

    def clear(self) -> None:
        self._providers.clear()


provider_registry = ProviderRegistry()
