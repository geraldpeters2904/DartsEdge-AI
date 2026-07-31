from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


@dataclass(frozen=True)
class ProviderCapabilities:
    competitions: bool = False
    players: bool = False
    fixtures: bool = False
    results: bool = False
    statistics: bool = False
    odds: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderHealth:
    status: str
    detail: str
    checked_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def healthy(self) -> bool:
        return self.status == "healthy"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "detail": self.detail,
            "healthy": self.healthy,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(frozen=True)
class CanonicalProviderRecord:
    entity_type: str
    external_id: str
    competition_code: str
    payload: Dict[str, Any]
    source_updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "external_id": self.external_id,
            "competition_code": self.competition_code,
            "payload": self.payload,
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
        }


class ProviderAdapter(ABC):
    provider_id: str
    display_name: str
    description: str
    capabilities: ProviderCapabilities
    supported_competitions: Set[str]

    @abstractmethod
    def health(self) -> ProviderHealth:
        raise NotImplementedError

    def competitions(self) -> Sequence[CanonicalProviderRecord]:
        return []

    def players(self) -> Sequence[CanonicalProviderRecord]:
        return []

    def fixtures(self, start_date: date, end_date: date) -> Sequence[CanonicalProviderRecord]:
        return []

    def results(self, start_date: date, end_date: date) -> Sequence[CanonicalProviderRecord]:
        return []

    def statistics(self, start_date: date, end_date: date) -> Sequence[CanonicalProviderRecord]:
        return []

    def describe(self) -> Dict[str, Any]:
        health = self.health()
        return {
            "id": self.provider_id,
            "name": self.display_name,
            "description": self.description,
            "capabilities": self.capabilities.to_dict(),
            "supported_competitions": sorted(self.supported_competitions),
            "health": health.to_dict(),
        }
