from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.ai_coach_service import build_ai_coach_data
from app.templates_config import templates


router = APIRouter()


@router.get("/ai-coach")
def ai_coach_page(request: Request):
    db = SessionLocal()
    try:
        coach = build_ai_coach_data(db)
        return templates.TemplateResponse(
            "ai_coach.html",
            {"request": request, **coach},
        )
    finally:
        db.close()
