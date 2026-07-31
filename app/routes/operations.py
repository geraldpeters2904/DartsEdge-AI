from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.current_capture_session_service import (
    CurrentCaptureSessionService,
)
from app.services.modus_capture_assistant_runtime import (
    capture_assistant_service,
)
from app.services.operations_dashboard_service import (
    OperationsDashboardService,
)
from app.templates_config import templates


router = APIRouter()
operations_service = OperationsDashboardService()
current_capture_service = CurrentCaptureSessionService()


def _redirect(capture_root: str, message: str):
    return RedirectResponse(
        (
            "/operations?capture_root="
            + quote(capture_root)
            + "&message="
            + quote(message)
        ),
        status_code=303,
    )


@router.get("/operations")
def operations_dashboard_page(
    request: Request,
    capture_root: str = "",
    db: Session = Depends(get_db),
):
    selected_root = capture_root or str(DEFAULT_CAPTURE_ROOT)

    dashboard = operations_service.build(
        db,
        capture_root=selected_root,
    )

    return templates.TemplateResponse(
        request,
        "operations_dashboard.html",
        {
            "dashboard": dashboard,
            "capture_root": selected_root,
            "message": request.query_params.get("message"),
        },
    )


@router.post("/operations/capture-assistant/start")
def start_operations_capture_assistant(
    capture_root: str = Form(...),
    watch_folder: str = Form("~/Downloads"),
):
    try:
        active_capture = current_capture_service.latest_incomplete(
            capture_root
        )

        if active_capture is None:
            raise ValueError(
                "No unfinished capture session was found."
            )

        capture_assistant_service.start(
            destination_folder=str(active_capture.folder),
            watch_folder=watch_folder,
        )

        return _redirect(
            capture_root,
            "Capture Assistant started.",
        )
    except Exception as exc:
        return _redirect(
            capture_root,
            "Could not start Capture Assistant: " + str(exc),
        )


@router.post("/operations/capture-assistant/stop")
def stop_operations_capture_assistant(
    capture_root: str = Form(...),
):
    capture_assistant_service.stop()

    return _redirect(
        capture_root,
        "Capture Assistant stopped.",
    )
