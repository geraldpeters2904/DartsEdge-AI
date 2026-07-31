from datetime import date
from typing import Sequence, Set

from app.providers.contracts import (
    CanonicalProviderRecord,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderHealth,
)


class ModusAdapter(ProviderAdapter):
    provider_id = "modus"
    display_name = "MODUS collector"
    description = "Provider SDK adapter reserved for an authorised MODUS ingestion source."
    capabilities = ProviderCapabilities(
        competitions=True,
        players=True,
        fixtures=True,
        results=True,
        statistics=True,
    )
    supported_competitions: Set[str] = {"MODUS"}

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def health(self) -> ProviderHealth:
        if not self.enabled:
            return ProviderHealth("disabled", "No authorised MODUS source has been configured.")
        return ProviderHealth("healthy", "MODUS adapter is enabled and ready for collector implementation.")

    def fixtures(self, start_date: date, end_date: date) -> Sequence[CanonicalProviderRecord]:
        if not self.enabled:
            return []
        return []
