from __future__ import annotations

from datetime import date, timedelta

from app.providers.manual import ManualDatabaseProvider
from app.providers.registry import ProviderRegistry


class DataProviderService:
    def __init__(self, db):
        self.db = db
        self.registry = ProviderRegistry()
        self.registry.register(ManualDatabaseProvider(db))

    def provider_status(self) -> list[dict]:
        statuses = []
        for provider in self.registry.all():
            health = provider.health()
            statuses.append(
                {
                    "id": provider.provider_id,
                    "name": provider.display_name,
                    "description": provider.description,
                    "status": health.status,
                    "detail": health.detail,
                    "capabilities": {
                        "fixtures": provider.capabilities.fixtures,
                        "results": provider.capabilities.results,
                        "odds": provider.capabilities.odds,
                    },
                }
            )
        return statuses

    def fixture_preview(self, provider_id: str = "manual", days: int = 7) -> dict:
        provider = self.registry.get(provider_id)
        start = date.today()
        end = start + timedelta(days=max(0, min(days, 31)))
        fixtures = list(provider.fetch_fixtures(start, end))
        return {
            "provider": provider.display_name,
            "start_date": start,
            "end_date": end,
            "count": len(fixtures),
            "fixtures": fixtures[:25],
        }

    def diagnostics(self) -> dict:
        providers = self.provider_status()
        healthy = sum(1 for item in providers if item["status"] == "healthy")
        return {
            "registered": len(providers),
            "healthy": healthy,
            "providers": providers,
        }
