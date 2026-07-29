from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.capture_wizard_service import CaptureWizardService
from app.templates_config import templates


router = APIRouter()
wizard_service = CaptureWizardService()


@router.get("/admin/collector/captures/new")
def capture_wizard_page(
    request: Request,
):
    return templates.TemplateResponse(
        request,
        "capture_wizard.html",
        {
            "default_root": str(DEFAULT_CAPTURE_ROOT),
            "message": request.query_params.get("message"),
            "result": None,
        },
    )


@router.post("/admin/collector/captures/new")
async def create_capture_sessions(
    request: Request,
    capture_root: str = Form(...),
    results_files: list[UploadFile] = File(...),
):
    try:
        saved_pages = []

        for upload in results_files:
            filename = (upload.filename or "").strip()
            if not filename:
                continue

            content = await upload.read()
            if not content:
                raise ValueError(f"{filename} is empty.")

            try:
                html = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"{filename} is not valid UTF-8 HTML."
                ) from exc

            saved_pages.append((filename, html))

        result = wizard_service.create_from_pages(
            capture_root=capture_root,
            saved_pages=saved_pages,
        )

        return templates.TemplateResponse(
            request,
            "capture_wizard.html",
            {
                "default_root": str(result.root),
                "message": None,
                "result": result,
            },
        )
    except Exception as exc:
        return RedirectResponse(
            (
                "/admin/collector/captures/new?message="
                + quote(f"Capture setup failed: {exc}")
            ),
            status_code=303,
        )
