from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.live_operations_centre_service import (
    build_live_ops_summary,
    recent_odds_movements,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/live-operations")
def live_operations_page(request: Request):
    db = SessionLocal()

    try:
        summary = build_live_ops_summary(db)
        movements = recent_odds_movements(
            db,
            limit=25,
        )

        return templates.TemplateResponse(
            "live_operations.html",
            {
                "request": request,
                "summary": summary,
                "movements": movements,
            },
        )
    finally:
        db.close()
