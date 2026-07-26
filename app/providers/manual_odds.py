from __future__ import annotations

from datetime import date
from typing import Iterable

from app.providers.base import DataProvider, OddsRecord, ProviderCapabilities, ProviderHealth


class ManualOddsProvider(DataProvider):
    provider_id = "manual-odds"
    display_name = "Manual odds"
    description = "Odds entered manually in DartsEdge AI (provider contract only in Pack 3)."
    capabilities = ProviderCapabilities(fixtures=False, results=False, odds=True)

    def health(self) -> ProviderHealth:
        return ProviderHealth("healthy", "Manual odds provider is available")

    def fetch_odds(self, start_date: date, end_date: date) -> Iterable[OddsRecord]:
        # Pack 3 establishes the contract. Persistence is introduced with the EV workflow.
        return []
