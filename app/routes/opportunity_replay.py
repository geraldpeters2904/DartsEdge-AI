from fastapi import APIRouter, HTTPException, Request

from app.db import SessionLocal
from app.services.opportunity_replay_service import (
    build_opportunity_replay,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/opportunities/{fixture_id}/replay")
def opportunity_replay_page(
    request: Request,
    fixture_id: int,
):
    db = SessionLocal()

    try:
        replay = build_opportunity_replay(
            db,
            fixture_id=fixture_id,
        )

        if replay is None:
            raise HTTPException(
                status_code=404,
                detail="Opportunity history not found.",
            )

        return templates.TemplateResponse(
            "opportunity_replay.html",
            {
                "request": request,
                "replay": replay,
            },
        )
    finally:
        db.close()
