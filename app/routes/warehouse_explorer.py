from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.services.warehouse_explorer_service import WarehouseExplorerService
from app.templates_config import templates


router = APIRouter()
explorer_service = WarehouseExplorerService()


def _redirect(path: str, message: str):
    return RedirectResponse(
        f"{path}?message={quote(message)}",
        status_code=303,
    )


@router.get("/admin/warehouse")
def warehouse_explorer_page(
    request: Request,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request,
        "warehouse_explorer.html",
        {
            "batches": explorer_service.list_batches(db),
            "message": request.query_params.get("message"),
        },
    )


@router.get("/admin/warehouse/batches/{batch_id}")
def warehouse_batch_detail_page(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    detail = explorer_service.batch_detail(db, batch_id)

    if detail is None:
        return _redirect(
            "/admin/warehouse",
            "Import batch not found.",
        )

    return templates.TemplateResponse(
        request,
        "warehouse_batch_detail.html",
        {
            "detail": detail,
            "message": request.query_params.get("message"),
        },
    )
