from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from app.providers.base import DataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: OrderedDict[str, DataProvider] = OrderedDict()

    def register(self, provider: DataProvider) -> None:
        provider_id = provider.provider_id.strip().lower()
        if not provider_id:
            raise ValueError("Provider id cannot be empty")
        if provider_id in self._providers:
            raise ValueError(f"Provider '{provider_id}' is already registered")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> DataProvider:
        try:
            return self._providers[provider_id.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"Unknown provider '{provider_id}'") from exc

    def all(self) -> Iterable[DataProvider]:
        return tuple(self._providers.values())
