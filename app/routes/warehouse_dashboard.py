from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.warehouse_dashboard_service import WarehouseDashboardService
from app.templates_config import templates


router = APIRouter()
dashboard_service = WarehouseDashboardService()


@router.get("/admin/warehouse-dashboard")
def warehouse_dashboard_page(
    request: Request,
    capture_root: str = "",
    db: Session = Depends(get_db),
):
    selected_root = capture_root or str(DEFAULT_CAPTURE_ROOT)
    dashboard = dashboard_service.build(db, capture_root=selected_root)

    return templates.TemplateResponse(
        request,
        "warehouse_dashboard.html",
        {
            "dashboard": dashboard,
            "capture_root": selected_root,
        },
    )
