from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.historical_import_manager_service import (
    HistoricalImportManagerService,
)
from app.templates_config import templates


router = APIRouter()
manager_service = HistoricalImportManagerService()


@router.get("/admin/historical-imports")
def historical_import_manager_page(
    request: Request,
    root: str = "",
    db: Session = Depends(get_db),
):
    selected_root = root or str(DEFAULT_CAPTURE_ROOT)
    library = None
    error = None

    try:
        library = manager_service.scan(db, selected_root)
    except Exception as exc:
        error = str(exc)

    return templates.TemplateResponse(
        request,
        "historical_import_manager.html",
        {
            "selected_root": selected_root,
            "library": library,
            "error": error,
        },
    )
