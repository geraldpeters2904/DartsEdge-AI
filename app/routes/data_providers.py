from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.data_provider_service import DataProviderService
from app.templates_config import templates


router = APIRouter()


@router.get("/data-providers")
def data_providers_page(request: Request):
    db = SessionLocal()
    try:
        service = DataProviderService(db)
        return templates.TemplateResponse(
            "data_providers.html",
            {
                "request": request,
                "providers": service.provider_status(),
                "preview": service.fixture_preview(),
            },
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
