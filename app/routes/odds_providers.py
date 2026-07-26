from fastapi import APIRouter, Request

from app.services.odds_provider_service import OddsProviderService
from app.templates_config import templates

router = APIRouter()


@router.get("/odds-providers")
def odds_providers_page(request: Request, provider: str = "remote-odds-json", days: int = 7):
    service = OddsProviderService()
    preview = None
    preview_error = None
    try:
        selected = service.registry.get(provider)
        if selected.health().status == "healthy":
            preview = service.preview(provider, days)
    except Exception as exc:
        preview_error = str(exc)
    return templates.TemplateResponse("odds_providers.html", {
        "request": request,
        "providers": service.provider_status(),
        "selected_provider": provider,
        "days": days,
        "preview": preview,
        "preview_error": preview_error,
    })


@router.get("/api/odds-providers")
def odds_providers_api():
    return OddsProviderService().diagnostics()
