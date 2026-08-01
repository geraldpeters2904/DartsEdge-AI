from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
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

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreview
from app.db import get_db
from app.models.historical_import import HistoricalImportPreview
from app.services.collector_preview_service import (
    CollectorPreviewService,
)
from app.services.historical_import_service import (
    batches,
    rollback_batch,
)
from app.templates_config import templates


router = APIRouter()
preview_service = CollectorPreviewService()
commit_bridge = CollectorCommitBridge()


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


def _rebuild_commit_preview(
    *,
    preview,
    mappings,
    session,
) -> CollectorFolderPreview:
    storage_payload = json.loads(preview.rows_json)
    filenames = storage_payload.get("filenames", {})

    discovered_files = {
        entity_type: Path(
            filenames.get(
                entity_type,
                f"{entity_type}.csv",
            )
        )
        for entity_type in mappings
    }

    supplied_filenames = {
        path.name
        for path in discovered_files.values()
    }

    missing_files = [
        item["filename"]
        for item in SUPPORTED_FILES
        if item["filename"] not in supplied_filenames
    ]

    return CollectorFolderPreview(
        folder=Path("collector-previews")
        / preview.preview_uuid,
        provider=preview.provider,
        discovered_files=discovered_files,
        mappings=mappings,
        session=session,
        missing_files=missing_files,
    )


@router.post(
    "/admin/collector/preview/{preview_uuid}/commit"
)
def commit_collector_preview(
    preview_uuid: str,
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

    if preview.status != "pending":
        return _redirect(
            f"/admin/collector/preview/{preview_uuid}",
            (
                "Only pending previews can be committed. "
                f"Current status: {preview.status}."
            ),
        )

    try:
        preview, mappings, session = preview_service.rebuild(
            db=db,
            preview_uuid=preview_uuid,
        )

        if not session.ready_to_commit:
            raise ValueError(
                "The preview is not ready to commit."
            )

        invalid_entities = [
            entity_type
            for entity_type, mapping in mappings.items()
            if not mapping.valid
        ]

        if invalid_entities:
            raise ValueError(
                "Invalid files remain in the preview: "
                + ", ".join(sorted(invalid_entities))
                + "."
            )

        commit_preview = _rebuild_commit_preview(
            preview=preview,
            mappings=mappings,
            session=session,
        )

        report = commit_bridge.commit(
            db=db,
            preview=commit_preview,
            filename=preview.filename,
        )

        preview.status = "committed"
        preview.batch_id = report.batch_id
        preview.committed_at = datetime.utcnow()

        db.commit()
        db.refresh(preview)

        counts = report.entity_counts

        return _redirect(
            "/admin/collector",
            (
                f"Batch {report.batch_uuid[:8]} committed: "
                f"{counts['fixtures']} fixtures, "
                f"{counts['results']} results, "
                f"{counts['statistics']} statistics and "
                f"{counts['odds']} odds received; "
                f"{report.rejected_rows} rejected."
            ),
        )

    except Exception as exc:
        db.rollback()

        return _redirect(
            f"/admin/collector/preview/{preview_uuid}",
            f"Commit failed: {exc}",
        )


@router.post(
    "/admin/collector/batches/{batch_id}/rollback"
)
def rollback_collector_batch(
    batch_id: int,
    db: Session = Depends(get_db),
):
    try:
        batch = rollback_batch(
            db,
            batch_id,
        )

        linked_previews = (
            db.query(HistoricalImportPreview)
            .filter_by(batch_id=batch.id)
            .all()
        )

        for preview in linked_previews:
            preview.status = "rolled_back"

        db.commit()

        return _redirect(
            "/admin/collector",
            f"Batch {batch.batch_uuid[:8]} rolled back.",
        )

    except Exception as exc:
        db.rollback()

        return _redirect(
            "/admin/collector",
            f"Rollback failed: {exc}",
        )
