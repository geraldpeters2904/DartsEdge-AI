from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.live_opportunity_centre_service import (
    build_live_opportunity_centre,
)
from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/mobile-opportunities")
def mobile_opportunities_page(
    request: Request,
):
    db = SessionLocal()

    try:
        payload = build_live_opportunity_centre(
            db,
            limit=30,
            persist=True,
        )

        readiness = (
            build_live_opportunity_pipeline_readiness(
                db,
                limit=30,
            )
        )

        return templates.TemplateResponse(
            "mobile_opportunities.html",
            {
                "request": request,
                **payload,
                "readiness": readiness,
            },
        )

    finally:
        db.close()
