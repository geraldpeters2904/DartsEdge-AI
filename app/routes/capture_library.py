from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.capture_library_service import (
    CaptureLibraryService,
    DEFAULT_CAPTURE_ROOT,
)
from app.templates_config import templates


router = APIRouter()
library_service = CaptureLibraryService()


@router.get("/admin/collector/captures")
def capture_library_page(
    request: Request,
    root: str = "",
):
    selected_root = root or str(DEFAULT_CAPTURE_ROOT)
    message = request.query_params.get("message")

    try:
        library = library_service.scan(selected_root)
    except Exception as exc:
        library = library_service.scan(DEFAULT_CAPTURE_ROOT)
        message = str(exc)

    grouped = {}
    for entry in library.entries:
        grouped.setdefault(entry.series_label, {})
        grouped[entry.series_label].setdefault(entry.week_label, [])
        grouped[entry.series_label][entry.week_label].append(entry)

    return templates.TemplateResponse(
        request,
        "capture_library.html",
        {
            "library": library,
            "grouped": grouped,
            "selected_root": selected_root,
            "message": message,
        },
    )
