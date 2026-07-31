from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.historical_operations_service import (
    HistoricalOperationsService,
)
from app.templates_config import templates


router = APIRouter()
historical_operations_service = HistoricalOperationsService()


@router.get("/admin/historical-operations")
def historical_operations_page(
    request: Request,
    root: str = "",
    db: Session = Depends(get_db),
):
    selected_root = root or str(DEFAULT_CAPTURE_ROOT)

    operations = historical_operations_service.build(
        db,
        root=selected_root,
    )

    return templates.TemplateResponse(
        request,
        "historical_operations.html",
        {
            "operations": operations,
            "root": selected_root,
        },
    )
