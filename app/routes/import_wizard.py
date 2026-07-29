from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.db import get_db
from app.services.collector_preview_service import CollectorPreviewService
from app.services.import_wizard_service import ImportWizardService
from app.templates_config import templates


router = APIRouter()
wizard_service = ImportWizardService()
preview_service = CollectorPreviewService()


def _redirect(path: str, message: str):
    return RedirectResponse(
        f"{path}?message={quote(message)}",
        status_code=303,
    )


@router.get("/admin/collector/import")
def import_wizard_page(
    request: Request,
):
    return templates.TemplateResponse(
        request,
        "import_wizard.html",
        {
            "connectors": wizard_service.connectors(),
            "message": request.query_params.get("message"),
            "validation": None,
            "selected_connector": "modus-official",
            "source_path": "",
            "allow_partial": False,
        },
    )


@router.post("/admin/collector/import/validate")
def validate_import_source(
    request: Request,
    connector_id: str = Form(...),
    source_path: str = Form(""),
    acceptance_mode: str = Form(""),
):
    try:
        connector = wizard_service.connector(connector_id)

        if connector.input_type == "redirect":
            return RedirectResponse(
                "/admin/collector",
                status_code=303,
            )

        allow_partial = acceptance_mode == "partial"
        manifest = wizard_service.validate_source(
            connector_id,
            source_path,
            allow_partial=allow_partial,
        )

        return templates.TemplateResponse(
            request,
            "import_wizard.html",
            {
                "connectors": wizard_service.connectors(),
                "message": None,
                "validation": manifest.to_dict(),
                "selected_connector": connector_id,
                "source_path": source_path,
                "allow_partial": allow_partial,
            },
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/import",
            f"Validation failed: {exc}",
        )


@router.post("/admin/collector/import/preview")
def create_connector_preview(
    connector_id: str = Form(...),
    source_path: str = Form(...),
    acceptance_mode: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        payload = wizard_service.build_preview_payload(
            connector_id,
            source_path,
            allow_partial=(acceptance_mode == "partial"),
        )

        preview = preview_service.create_preview(
            db=db,
            provider=payload["provider"],
            competition=payload["competition"],
            csv_by_type=payload["csv_by_type"],
            filenames=payload["filenames"],
        )

        return RedirectResponse(
            f"/admin/collector/preview/{preview.preview_uuid}",
            status_code=303,
        )
    except Exception as exc:
        return _redirect(
            "/admin/collector/import",
            f"Preview failed: {exc}",
        )
