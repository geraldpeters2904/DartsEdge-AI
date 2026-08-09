from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.forward_fixture_catchup_service import (
    resolve_fixture_refresh_callable,
    stale_scheduled_modus_fixtures,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/fixture-catchup")
def fixture_catchup_page(
    request: Request,
):
    db = SessionLocal()

    try:
        candidates = (
            stale_scheduled_modus_fixtures(
                db,
                limit=200,
            )
        )

        resolution = (
            resolve_fixture_refresh_callable()
        )

        return templates.TemplateResponse(
            "forward_fixture_catchup.html",
            {
                "request": request,
                "candidates": candidates,
                "candidate_count": len(
                    candidates
                ),
                "resolution": resolution,
            },
        )

    finally:
        db.close()
