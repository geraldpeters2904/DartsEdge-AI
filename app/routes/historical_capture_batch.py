from __future__ import annotations

from typing import List
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchService,
)
from app.templates_config import templates


router = APIRouter()
batch_service = HistoricalCaptureBatchService()


def _redirect(root: str, message: str):
    return RedirectResponse(
        (
            "/admin/historical-capture-batch?root="
            + quote(root)
            + "&message="
            + quote(message)
        ),
        status_code=303,
    )


@router.get("/admin/historical-capture-batch")
def historical_capture_batch_page(
    request: Request,
    root: str = "",
):
    batch = None
    error = None

    if root:
        try:
            batch = batch_service.load(root)
        except Exception as exc:
            error = str(exc)

    return templates.TemplateResponse(
        request,
        "historical_capture_batch.html",
        {
            "batch": batch,
            "root": root,
            "error": error,
            "message": request.query_params.get("message"),
        },
    )


@router.post("/admin/historical-capture-batch/build")
async def build_historical_capture_batch(
    root: str = Form(...),
    results_files: List[UploadFile] = File(...),
):
    try:
        pages = []

        for upload in results_files:
            filename = (upload.filename or "").strip()

            if not filename:
                continue

            content = await upload.read()

            if not content:
                raise ValueError(
                    f"Selected results page is empty: {filename}"
                )

            try:
                html = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(
                    f"Results page is not valid UTF-8 HTML: {filename}"
                ) from exc

            pages.append((filename, html))

        if not pages:
            raise ValueError(
                "Choose at least one saved MODUS results page."
            )

        batch = batch_service.create(
            root=root,
            results_pages=pages,
        )

        return _redirect(
            str(batch.root),
            (
                f"Historical capture batch created with "
                f"{batch.total_groups} group(s)."
            ),
        )
    except Exception as exc:
        return _redirect(
            root,
            "Could not build historical capture batch: " + str(exc),
        )


@router.post("/admin/historical-capture-batch/refresh")
def refresh_historical_capture_batch(
    root: str = Form(...),
):
    try:
        batch = batch_service.refresh(root)

        return _redirect(
            str(batch.root),
            "Historical capture batch refreshed.",
        )
    except Exception as exc:
        return _redirect(
            root,
            "Could not refresh historical capture batch: " + str(exc),
        )


@router.post("/admin/historical-capture-batch/clear")
def clear_historical_capture_batch(
    root: str = Form(...),
):
    try:
        removed = batch_service.clear(root)

        return _redirect(
            root,
            (
                "Batch manifest cleared. Capture folders were preserved."
                if removed
                else "No batch manifest existed for this root."
            ),
        )
    except Exception as exc:
        return _redirect(
            root,
            "Could not clear historical capture batch: " + str(exc),
        )
