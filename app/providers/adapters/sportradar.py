import os
from typing import Set

from app.providers.contracts import ProviderAdapter, ProviderCapabilities, ProviderHealth


class SportradarAdapter(ProviderAdapter):
    provider_id = "sportradar"
    display_name = "Sportradar"
    description = "Optional commercial adapter. Coverage must be confirmed before activation."
    capabilities = ProviderCapabilities(
        competitions=True,
        players=True,
        fixtures=True,
        results=True,
        statistics=True,
    )
    supported_competitions: Set[str] = {"MODUS", "PDC", "WDF", "ADC", "CDC", "OTHER"}

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.getenv("DARTSEDGE_SPORTRADAR_API_KEY", "")

    def health(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth("disabled", "No Sportradar API key is configured.")
        return ProviderHealth("configured", "API key present; coverage and endpoint access still require validation.")
