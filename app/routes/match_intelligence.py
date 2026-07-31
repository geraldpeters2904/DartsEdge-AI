from fastapi import APIRouter, HTTPException, Request

from app.db import SessionLocal
from app.services.match_intelligence_workspace_service import build_match_intelligence
from app.templates_config import templates

router = APIRouter()


@router.get("/match-intelligence/{fixture_id}")
def match_intelligence_page(request: Request, fixture_id: int):
    db = SessionLocal()
    try:
        payload = build_match_intelligence(db, fixture_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Fixture not found")
        return templates.TemplateResponse(
            "match_intelligence.html",
            {"request": request, **payload},
        )
    finally:
        db.close()
