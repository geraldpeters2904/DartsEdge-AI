
from fastapi import APIRouter, Request

from app.services.live_edge_monitor_service import (
    live_edge_monitor,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/live-edge-monitor")
def live_edge_monitor_page(
    request: Request,
):
    return templates.TemplateResponse(
        "live_edge_monitor.html",
        {
            "request": request,
            "status": live_edge_monitor.status(),
        },
    )


@router.post("/live-edge-monitor/run-once")
def live_edge_monitor_run_once(
    request: Request,
):
    return templates.TemplateResponse(
        "live_edge_monitor.html",
        {
            "request": request,
            "status": live_edge_monitor.run_once(),
        },
    )
