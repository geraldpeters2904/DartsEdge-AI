
from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.live_fixture_edge_capture_service import (
    run_live_fixture_edge_capture,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/live-edge-capture")
def live_edge_capture_page(
    request: Request,
):
    return templates.TemplateResponse(
        "live_fixture_edge_capture.html",
        {
            "request": request,
            "report": None,
        },
    )


@router.post("/live-edge-capture/run")
def live_edge_capture_run(
    request: Request,
):
    db = SessionLocal()

    try:
        report = run_live_fixture_edge_capture(
            db
        )

        return templates.TemplateResponse(
            "live_fixture_edge_capture.html",
            {
                "request": request,
                "report": report,
            },
        )
    finally:
        db.close()
