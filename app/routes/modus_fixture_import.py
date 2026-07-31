from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.services.collector_preview_service import CollectorPreviewService
from app.services.modus_fixture_import_service import (
    ModusFixtureImportService,
)
from app.templates_config import templates


router = APIRouter()
fixture_import_service = ModusFixtureImportService()
preview_service = CollectorPreviewService()


def _redirect(path: str, message: str):
    return RedirectResponse(
        f"{path}?message={quote(message)}",
        status_code=303,
    )


@router.get("/admin/collector/import/modus-fixtures")
def modus_fixture_import_page(
    request: Request,
):
    return templates.TemplateResponse(
        request,
        "modus_fixture_import.html",
        {
            "message": request.query_params.get("message"),
        },
    )


@router.post("/admin/collector/import/modus-fixtures/preview")
async def create_modus_fixture_preview(
    results_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        filename = (results_file.filename or "").strip()
        if not filename:
            raise ValueError("Choose a saved MODUS results or fixtures page.")

        content = await results_file.read()
        if not content:
            raise ValueError("The selected page is empty.")

        try:
            html = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "The saved page is not valid UTF-8 HTML."
            ) from exc

        payload = fixture_import_service.build_payload(html)

        preview = preview_service.create_preview(
            db=db,
            provider="modus-official",
            competition="MODUS",
            csv_by_type=payload.csv_by_type,
            filenames=payload.filenames,
        )

        return RedirectResponse(
            f"/admin/collector/preview/{preview.preview_uuid}",
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/import/modus-fixtures",
            f"Fixture preview failed: {exc}",
        )
