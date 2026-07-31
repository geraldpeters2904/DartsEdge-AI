from app.providers.adapters import ModusAdapter, SportradarAdapter
from app.providers.registry import provider_registry


def register_default_providers() -> None:
    existing = {provider.provider_id for provider in provider_registry.all()}
    for provider in (ModusAdapter(), SportradarAdapter()):
        if provider.provider_id not in existing:
            provider_registry.register(provider)
