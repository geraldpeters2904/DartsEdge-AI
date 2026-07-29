from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List
from urllib.parse import quote

from app.db import get_db
from app.services.historical_import_queue_service import HistoricalImportQueueService
from app.templates_config import templates

router = APIRouter()
queue_service = HistoricalImportQueueService()

def _redirect(path: str, message: str):
    separator = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{separator}message={quote(message)}", status_code=303)

@router.post("/admin/historical-imports/queue")
def create_historical_import_queue(root: str = Form(...), selected_folders: List[str] = Form([])):
    try:
        queue_service.create(root=root, selected_folders=selected_folders)
        return RedirectResponse("/admin/historical-imports/queue?root=" + quote(root), status_code=303)
    except Exception as exc:
        return _redirect("/admin/historical-imports?root=" + quote(root), f"Queue creation failed: {exc}")

@router.get("/admin/historical-imports/queue")
def historical_import_queue_page(request: Request, root: str, db: Session = Depends(get_db)):
    queue = None; error = None
    try: queue = queue_service.load(db, root)
    except Exception as exc: error = str(exc)
    return templates.TemplateResponse(request, "historical_import_queue.html", {
        "queue": queue, "root": root, "error": error,
        "message": request.query_params.get("message"),
    })

@router.post("/admin/historical-imports/queue/clear")
def clear_historical_import_queue(root: str = Form(...)):
    queue_service.clear(root)
    return _redirect("/admin/historical-imports?root=" + quote(root), "Historical import queue cleared.")
