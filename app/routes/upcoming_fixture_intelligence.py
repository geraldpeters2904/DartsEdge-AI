from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.upcoming_fixture_intelligence_service import (
    build_upcoming_fixture_intelligence,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/upcoming-fixtures")
def upcoming_fixture_intelligence_page(
    request: Request,
):
    db = SessionLocal()

    try:
        fixtures = (
            build_upcoming_fixture_intelligence(
                db
            )
        )

        ready_count = sum(
            item.history_ready
            for item in fixtures
        )

        return templates.TemplateResponse(
            "upcoming_fixture_intelligence.html",
            {
                "request": request,
                "fixtures": fixtures,
                "fixture_count": len(
                    fixtures
                ),
                "ready_count": int(
                    ready_count
                ),
            },
        )

    finally:
        db.close()
