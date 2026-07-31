from sqlalchemy.orm import Session

from app.models.provider_sync import ProviderSyncRun
from app.providers.bootstrap import register_default_providers
from app.providers.registry import provider_registry


def build_provider_admin(db: Session):
    register_default_providers()
    providers = [provider.describe() for provider in provider_registry.all()]
    runs = (
        db.query(ProviderSyncRun)
        .order_by(ProviderSyncRun.started_at.desc(), ProviderSyncRun.id.desc())
        .limit(25)
        .all()
    )
    return {
        "architecture": "provider-independent",
        "registered": len(providers),
        "providers": providers,
        "runs": runs,
    }
