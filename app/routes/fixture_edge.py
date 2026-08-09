from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.fixture_edge_service import (
    build_fixture_edge_rows,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/fixture-edge")
def fixture_edge_page(
    request: Request,
):
    db = SessionLocal()

    try:
        rows = (
            build_fixture_edge_rows(
                db
            )
        )

        return templates.TemplateResponse(
            "fixture_edge.html",
            {
                "request": request,
                "rows": rows,
                "row_count": len(
                    rows
                ),
            },
        )
    finally:
        db.close()
