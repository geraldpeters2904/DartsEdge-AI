from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.shadow_comparison_service import build_shadow_comparison, record_outcome
from app.templates_config import templates

router = APIRouter()


@router.get("/shadow-comparison")
def shadow_comparison_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse("shadow_comparison.html", {
            "request": request,
            "comparison": build_shadow_comparison(db),
        })
    finally:
        db.close()


@router.post("/shadow-comparison/{audit_uuid}/settle")
def settle_shadow_prediction(audit_uuid: str, actual_winner: str = Form(...)):
    db = SessionLocal()
    try:
        record_outcome(db, audit_uuid, actual_winner)
        return RedirectResponse("/shadow-comparison", status_code=303)
    finally:
        db.close()
