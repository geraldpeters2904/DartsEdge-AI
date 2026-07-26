from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ProviderCapabilities:
    fixtures: bool = False
    results: bool = False
    odds: bool = False


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    detail: str


@dataclass(frozen=True)
class FixtureRecord:
    event_date: date
    tournament: str
    stage: str
    match_format: str
    player_a: str
    player_b: str
    external_id: str | None = None
    source_metadata: Mapping[str, Any] = field(default_factory=dict)

    def natural_key(self) -> tuple[str, str, str, str]:
        return (
            self.event_date.isoformat(),
            self.tournament.strip().casefold(),
            self.player_a.strip().casefold(),
            self.player_b.strip().casefold(),
        )


class DataProvider(ABC):
    provider_id: str
    display_name: str
    description: str
    capabilities: ProviderCapabilities

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    def fetch_fixtures(self, start_date: date, end_date: date) -> Iterable[FixtureRecord]:
        if not self.capabilities.fixtures:
            raise NotImplementedError(f"{self.display_name} does not provide fixtures")
        return []
