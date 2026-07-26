from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.templates_config import templates


router = APIRouter()


@router.get("/opportunities")
def opportunities_page(request: Request):
    db = SessionLocal()

    try:
        opportunities = build_ranked_opportunities(db, limit=50)
        confirmed_value_count = sum(
            1 for opportunity in opportunities
            if opportunity["is_value_confirmed"]
        )

        return templates.TemplateResponse(
            "opportunities.html",
            {
                "request": request,
                "opportunities": opportunities,
                "opportunity_count": len(opportunities),
                "confirmed_value_count": confirmed_value_count,
            },
        )
    finally:
        db.close()
