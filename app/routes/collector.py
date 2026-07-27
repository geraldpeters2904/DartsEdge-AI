from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Request,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.collector_preview_service import (
    CollectorPreviewService,
)
from app.services.historical_import_service import batches
from app.templates_config import templates


router = APIRouter()
preview_service = CollectorPreviewService()


SUPPORTED_FILES = (
    {
        "entity_type": "fixtures",
        "filename": "fixtures.csv",
        "label": "Fixtures",
        "description": (
            "Scheduled matches, competition details and participants."
        ),
        "icon": "📅",
    },
    {
        "entity_type": "results",
        "filename": "results.csv",
        "label": "Results",
        "description": (
            "Final scores, winners, first-leg winners and first 180s."
        ),
        "icon": "🏁",
    },
    {
        "entity_type": "statistics",
        "filename": "statistics.csv",
        "label": "Statistics",
        "description": (
            "Player averages, scoring, checkout and leg statistics."
        ),
        "icon": "📊",
    },
    {
        "entity_type": "odds",
        "filename": "odds.csv",
        "label": "Odds",
        "description": (
            "Immutable bookmaker market-price observations."
        ),
        "icon": "💷",
    },
)


COMPETITIONS = (
    ("MODUS", "MODUS Super Series"),
    ("PDC", "Professional Darts Corporation"),
    ("WDF", "World Darts Federation"),
    ("ADC", "Amateur Darts Circuit"),
    ("CDC", "Championship Darts Corporation"),
    ("OTHER", "Other competition"),
)


def _redirect(path: str, message: str):
    return RedirectResponse(
        f"{path}?message={quote(message)}",
        status_code=303,
    )


async def _read_upload(
    upload: Optional[UploadFile],
):
    if upload is None:
        return None

    filename = (upload.filename or "").strip()

    if not filename:
        return None

    content = await upload.read()

    if not content:
        return None

    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"{filename} is not valid UTF-8 CSV data."
        ) from exc

    return filename, csv_text


@router.get("/admin/collector")
def collector_page(
    request: Request,
    db: Session = Depends(get_db),
):
    recent_batches = batches(db, limit=15)

    imported_batches = sum(
        1
        for batch in recent_batches
        if batch.status == "imported"
    )
    rolled_back_batches = sum(
        1
        for batch in recent_batches
        if batch.status == "rolled_back"
    )
    received_records = sum(
        int(batch.received_rows or 0)
        for batch in recent_batches
    )

    return templates.TemplateResponse(
        request,
        "collector.html",
        {
            "supported_files": SUPPORTED_FILES,
            "competitions": COMPETITIONS,
            "batches": recent_batches,
            "message": request.query_params.get("message"),
            "dashboard": {
                "recent_batches": len(recent_batches),
                "imported_batches": imported_batches,
                "rolled_back_batches": rolled_back_batches,
                "received_records": received_records,
            },
        },
    )


@router.post("/admin/collector/preview")
async def create_collector_preview(
    provider: str = Form("manual-research"),
    competition: str = Form("MODUS"),
    fixtures_file: Optional[UploadFile] = File(None),
    results_file: Optional[UploadFile] = File(None),
    statistics_file: Optional[UploadFile] = File(None),
    odds_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    uploads = {
        "fixtures": fixtures_file,
        "results": results_file,
        "statistics": statistics_file,
        "odds": odds_file,
    }

    csv_by_type = {}
    filenames = {}

    try:
        for entity_type, upload in uploads.items():
            uploaded = await _read_upload(upload)

            if uploaded is None:
                continue

            filename, csv_text = uploaded
            csv_by_type[entity_type] = csv_text
            filenames[entity_type] = filename

        preview = preview_service.create_preview(
            db=db,
            provider=provider,
            competition=competition,
            csv_by_type=csv_by_type,
            filenames=filenames,
        )

        return RedirectResponse(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}"
            ),
            status_code=303,
        )

    except Exception as exc:
        return _redirect(
            "/admin/collector",
            f"Preview failed: {exc}",
        )


@router.get("/admin/collector/preview/{preview_uuid}")
def collector_preview_page(
    preview_uuid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    preview = preview_service.get_preview(
        db=db,
        preview_uuid=preview_uuid,
    )

    if preview is None:
        return _redirect(
            "/admin/collector",
            "Collector preview not found.",
        )

    report = preview_service.preview_report(
        db=db,
        preview_uuid=preview_uuid,
    )

    return templates.TemplateResponse(
        request,
        "collector_preview.html",
        {
            "preview": preview,
            "report": report,
            "supported_files": SUPPORTED_FILES,
            "message": request.query_params.get("message"),
        },
    )


@router.post(
    "/admin/collector/preview/{preview_uuid}/cancel"
)
def cancel_collector_preview(
    preview_uuid: str,
    db: Session = Depends(get_db),
):
    try:
        preview_service.cancel_preview(
            db=db,
            preview_uuid=preview_uuid,
        )

        return _redirect(
            "/admin/collector",
            "Collector preview cancelled. No warehouse data was changed.",
        )

    except Exception as exc:
        return _redirect(
            "/admin/collector",
            f"Unable to cancel preview: {exc}",
        )
