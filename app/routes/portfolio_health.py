from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.portfolio_health_service import build_portfolio_health
from app.templates_config import templates


router = APIRouter()


@router.get("/portfolio-health")
def portfolio_health_page(request: Request):
    db = SessionLocal()
    try:
        portfolio = build_portfolio_health(db)
        return templates.TemplateResponse(
            "portfolio_health.html",
            {"request": request, **portfolio},
        )
    finally:
        db.close()
