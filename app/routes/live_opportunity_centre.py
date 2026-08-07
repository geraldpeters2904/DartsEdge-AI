from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.live_opportunity_centre_service import (
    build_live_opportunity_centre,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/opportunities")
def opportunities_page(
    request: Request,
):
    db = SessionLocal()

    try:
        payload = build_live_opportunity_centre(
            db,
            limit=50,
            persist=True,
        )

        return templates.TemplateResponse(
            "live_opportunity_centre.html",
            {
                "request": request,
                **payload,
            },
        )
    finally:
        db.close()
