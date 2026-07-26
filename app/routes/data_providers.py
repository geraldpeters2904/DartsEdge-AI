from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.data_provider_service import DataProviderService
from app.services.fixture_import_service import FixtureImportService
from app.templates_config import templates

router = APIRouter()


@router.get("/data-providers")
def data_providers_page(request: Request, provider: str = "remote-json", days: int = 7):
    db = SessionLocal()
    try:
        provider_service = DataProviderService(db)
        preview = None
        preview_error = None
        try:
            if provider == "manual" or provider_service.registry.get(provider).health().status == "healthy":
                preview = FixtureImportService(db, provider_service).preview(provider, days)
        except Exception as exc:
            preview_error = str(exc)
        return templates.TemplateResponse("data_providers.html", {
            "request": request,
            "providers": provider_service.provider_status(),
            "preview": preview,
            "preview_error": preview_error,
            "selected_provider": provider,
            "days": days,
            "import_result": request.query_params.get("result"),
        })
    finally:
        db.close()


@router.post("/data-providers/import")
def import_provider_fixtures(provider_id: str = Form(...), days: int = Form(7)):
    db = SessionLocal()
    try:
        provider_service = DataProviderService(db)
        report = FixtureImportService(db, provider_service).import_fixtures(provider_id, days)
        result = (
            f"Imported {report.created}; skipped {report.skipped_duplicates} duplicates; "
            f"created {report.players_created} players."
        )
        return RedirectResponse(
            f"/data-providers?provider={provider_id}&days={days}&result={result}",
            status_code=303,
        )
    finally:
        db.close()


@router.get("/api/data-providers")
def data_providers_api():
    db = SessionLocal()
    try:
        return DataProviderService(db).diagnostics()
    finally:
        db.close()
