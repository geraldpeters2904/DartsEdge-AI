from __future__ import annotations

from datetime import date, timedelta

from app.providers.manual_odds import ManualOddsProvider
from app.providers.registry import ProviderRegistry
from app.providers.remote_odds_json import RemoteJsonOddsProvider


class OddsProviderService:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.registry.register(ManualOddsProvider())
        self.registry.register(RemoteJsonOddsProvider())

    def provider_status(self) -> list[dict]:
        rows = []
        for provider in self.registry.all():
            if not provider.capabilities.odds:
                continue
            health = provider.health()
            rows.append({
                "id": provider.provider_id,
                "name": provider.display_name,
                "description": provider.description,
                "status": health.status,
                "detail": health.detail,
                "capabilities": {"odds": provider.capabilities.odds},
            })
        return rows

    def preview(self, provider_id: str = "remote-odds-json", days: int = 7) -> dict:
        provider = self.registry.get(provider_id)
        start = date.today()
        end = start + timedelta(days=max(0, min(days, 31)))
        records = list(provider.fetch_odds(start, end))
        return {
            "provider": provider,
            "start_date": start,
            "end_date": end,
            "count": len(records),
            "records": records[:100],
        }

    def diagnostics(self) -> dict:
        providers = self.provider_status()
        return {
            "registered": len(providers),
            "healthy": sum(1 for row in providers if row["status"] == "healthy"),
            "providers": providers,
        }
