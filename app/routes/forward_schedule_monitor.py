
from fastapi import APIRouter, Request

from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.templates_config import templates

router = APIRouter()


@router.get("/forward-monitor")
def forward_monitor_page(request: Request):
    return templates.TemplateResponse(
        "forward_schedule_monitor.html",
        {
            "request": request,
            "status": forward_schedule_monitor.status(),
        },
    )


@router.post("/forward-monitor/run-once")
def forward_monitor_run_once(request: Request):
    return templates.TemplateResponse(
        "forward_schedule_monitor.html",
        {
            "request": request,
            "status": forward_schedule_monitor.run_once(),
        },
    )
