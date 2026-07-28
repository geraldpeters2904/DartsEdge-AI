from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)
from app.templates_config import templates


router = APIRouter()
capture_service = ModusCaptureSessionService()


def _redirect(path: str, message: str):
    return RedirectResponse(
        f"{path}?message={quote(message)}",
        status_code=303,
    )


@router.get("/admin/collector/capture/modus")
def capture_manager_page(
    request: Request,
    folder: str = "",
):
    session = None
    message = request.query_params.get("message")

    if folder:
        try:
            session = capture_service.load_session(folder)
        except Exception as exc:
            message = str(exc)

    return templates.TemplateResponse(
        request,
        "modus_capture_manager.html",
        {
            "session": session,
            "destination_folder": folder,
            "message": message,
        },
    )


@router.post("/admin/collector/capture/modus/build")
async def build_capture_queue(
    results_file: UploadFile = File(...),
    destination_folder: str = Form(...),
):
    try:
        filename = (results_file.filename or "").strip()
        if not filename:
            raise ValueError("Choose a saved MODUS results HTML file.")

        content = await results_file.read()
        if not content:
            raise ValueError("The selected results file is empty.")

        try:
            html = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "The saved results page is not valid UTF-8 HTML."
            ) from exc

        session = capture_service.create_session(
            results_filename=filename,
            results_html=html,
            destination_folder=destination_folder,
        )

        return RedirectResponse(
            (
                "/admin/collector/capture/modus?folder="
                + quote(str(session.destination_folder))
            ),
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/capture/modus",
            f"Unable to build capture queue: {exc}",
        )


@router.post("/admin/collector/capture/modus/refresh")
def refresh_capture_queue(
    destination_folder: str = Form(...),
):
    try:
        session = capture_service.refresh_session(destination_folder)

        return RedirectResponse(
            (
                "/admin/collector/capture/modus?folder="
                + quote(str(session.destination_folder))
            ),
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/capture/modus",
            f"Unable to refresh capture queue: {exc}",
        )
