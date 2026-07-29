from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.services.historical_import_engine_service import (
    HistoricalImportEngineService,
)
from app.templates_config import templates


router = APIRouter()
service = HistoricalImportEngineService()


@router.post("/admin/historical-imports/engine/start")
def start_engine(root: str = Form(...), db: Session = Depends(get_db)):
    service.start(db, root)
    return RedirectResponse(
        "/admin/historical-imports/engine?root=" + quote(root),
        status_code=303,
    )


@router.get("/admin/historical-imports/engine")
def engine_page(
    request: Request,
    root: str,
    db: Session = Depends(get_db),
):
    state = None
    error = None
    try:
        state = service.load(db, root)
    except Exception as exc:
        error = str(exc)

    return templates.TemplateResponse(
        request,
        "historical_import_engine.html",
        {
            "state": state,
            "root": root,
            "audit": service.audit(root),
            "error": error,
        },
    )


@router.post("/admin/historical-imports/engine/next")
def open_next(root: str = Form(...), db: Session = Depends(get_db)):
    state = service.begin_next(db, root)
    if state.next_item is None:
        return RedirectResponse(
            "/admin/historical-imports/engine?root=" + quote(root),
            status_code=303,
        )
    return RedirectResponse(
        state.next_item.folder.import_url,
        status_code=303,
    )
