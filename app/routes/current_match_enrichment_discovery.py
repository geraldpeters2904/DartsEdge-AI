
from fastapi import APIRouter, Request

from app.services.current_match_enrichment_discovery_service import (
    run_current_match_enrichment_discovery,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/current-enrichment-discovery")
def current_enrichment_discovery_page(
    request: Request,
):
    report = (
        run_current_match_enrichment_discovery()
    )

    return templates.TemplateResponse(
        "current_match_enrichment_discovery.html",
        {
            "request": request,
            "report": report,
        },
    )
