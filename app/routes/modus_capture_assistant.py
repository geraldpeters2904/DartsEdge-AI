from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from app.services.modus_capture_assistant_service import (
    ModusCaptureAssistantService,
)
from app.templates_config import templates


router = APIRouter()
assistant_service = ModusCaptureAssistantService()


def _redirect(message: str = ""):
    path = "/admin/collector/capture/modus/assistant"
    if message:
        path += "?message=" + quote(message)
    return RedirectResponse(path, status_code=303)


@router.get("/admin/collector/capture/modus/assistant")
def capture_assistant_page(request: Request):
    return templates.TemplateResponse(
        request,
        "modus_capture_assistant.html",
        {
            "status": assistant_service.status(),
            "message": request.query_params.get("message"),
        },
    )


@router.get("/admin/collector/capture/modus/assistant/status")
def capture_assistant_status():
    return assistant_service.status()


@router.post("/admin/collector/capture/modus/assistant/start")
def start_capture_assistant(
    destination_folder: str = Form(...),
    watch_folder: str = Form("~/Downloads"),
):
    try:
        assistant_service.start(
            destination_folder=destination_folder,
            watch_folder=watch_folder,
        )
        return _redirect("Assisted capture started.")
    except Exception as exc:
        return _redirect("Could not start assistant: " + str(exc))


@router.post("/admin/collector/capture/modus/assistant/stop")
def stop_capture_assistant():
    assistant_service.stop()
    return _redirect("Assisted capture stopped.")
