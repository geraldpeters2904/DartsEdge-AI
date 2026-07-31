from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.collector.service import CollectorService
from app.db import get_db
from app.services.provider_admin_service import build_provider_admin
from app.templates_config import templates

router = APIRouter(tags=["Provider SDK"])


@router.get("/admin/providers")
def provider_admin_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "provider_admin.html",
        {"request": request, **build_provider_admin(db)},
    )


@router.get("/api/providers")
def provider_admin_api(db: Session = Depends(get_db)):
    data = build_provider_admin(db)
    return {
        "architecture": data["architecture"],
        "registered": data["registered"],
        "providers": data["providers"],
        "recent_runs": [
            {
                "id": run.id,
                "provider_id": run.provider_id,
                "operation": run.operation,
                "status": run.status,
                "records_received": run.records_received,
                "records_accepted": run.records_accepted,
                "error": run.error_detail,
            }
            for run in data["runs"]
        ],
    }


@router.post("/admin/providers/{provider_id}/run")
def run_provider(
    provider_id: str,
    operation: str = Form(...),
    db: Session = Depends(get_db),
):
    result = CollectorService().run(db, provider_id, operation, date.today(), date.today())
    message = result.get("error") or f"{operation} completed: {result['records']} records"
    return RedirectResponse(
        url=f"/admin/providers?status={result['status']}&message={message}",
        status_code=303,
    )
