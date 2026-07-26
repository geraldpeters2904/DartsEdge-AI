from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.daily_briefing_service import build_daily_briefing
from app.templates_config import templates

router = APIRouter()


@router.get("/daily-briefing")
def daily_briefing_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            "daily_briefing.html",
            {"request": request, **build_daily_briefing(db)},
        )
    finally:
        db.close()
