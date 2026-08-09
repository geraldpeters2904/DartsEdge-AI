from fastapi import APIRouter, Request

from app.services.modus_match_id_diagnostic_service import (
    run_modus_match_id_diagnostic,
)
from app.templates_config import templates

router = APIRouter()


@router.get("/modus-match-id-diagnostic")
def modus_match_id_diagnostic_page(request: Request):
    report = run_modus_match_id_diagnostic()

    return templates.TemplateResponse(
        "modus_match_id_diagnostic.html",
        {
            "request": request,
            "report": report,
        },
    )
