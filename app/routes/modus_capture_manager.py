from __future__ import annotations

from pathlib import Path
import subprocess
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)
from app.services.modus_folder_service import ModusFolderImportService
from app.templates_config import templates


router = APIRouter()
capture_service = ModusCaptureSessionService()
folder_service = ModusFolderImportService()


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
    validation = None
    message = request.query_params.get("message")

    if folder:
        try:
            session = capture_service.load_session(folder)
            if session.complete:
                validation = folder_service.inspect(folder).to_dict()
        except Exception as exc:
            message = str(exc)

    return templates.TemplateResponse(
        request,
        "modus_capture_manager.html",
        {
            "session": session,
            "validation": validation,
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


@router.post("/admin/collector/capture/modus/open-folder")
def open_capture_folder(
    destination_folder: str = Form(...),
):
    try:
        folder = Path(destination_folder).expanduser().resolve()
        if not folder.exists() or not folder.is_dir():
            raise ValueError("Capture folder does not exist.")

        subprocess.run(
            ["open", str(folder)],
            check=True,
            timeout=10,
        )

        return RedirectResponse(
            (
                "/admin/collector/capture/modus?folder="
                + quote(str(folder))
                + "&message="
                + quote("Capture folder opened in Finder.")
            ),
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/capture/modus",
            f"Unable to open folder: {exc}",
        )


@router.post("/admin/collector/capture/modus/validate")
def validate_capture_folder(
    destination_folder: str = Form(...),
):
    try:
        manifest = folder_service.inspect(destination_folder)
        message = (
            "Capture folder is ready for import."
            if manifest.ready
            else "Capture folder still has validation issues."
        )

        return RedirectResponse(
            (
                "/admin/collector/capture/modus?folder="
                + quote(str(manifest.folder))
                + "&message="
                + quote(message)
            ),
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/capture/modus",
            f"Validation failed: {exc}",
        )
