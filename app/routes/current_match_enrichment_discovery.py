from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.current_match_enrichment_discovery_service import (
    run_current_match_enrichment_discovery,
)
from app.services.current_match_enrichment_workflow_service import (
    CurrentMatchEnrichmentWorkflowService,
)
from app.templates_config import templates


router = APIRouter()
workflow_service = CurrentMatchEnrichmentWorkflowService()


def _redirect(message: str):
    return RedirectResponse(
        (
            "/current-enrichment-discovery"
            "?message="
            + quote(message)
        ),
        status_code=303,
    )


def _resolved_candidate_for_match(
    report,
    internal_match_id: int,
):
    candidates = tuple(
        getattr(
            report,
            "candidates",
            (),
        )
        or ()
    )

    candidate = next(
        (
            row
            for row in candidates
            if int(row.internal_match_id)
            == int(internal_match_id)
        ),
        None,
    )

    if candidate is None:
        raise ValueError(
            "This match is no longer present in the "
            "current enrichment discovery results."
        )

    if candidate.status != "resolved":
        raise ValueError(
            "This match is not currently resolved to one "
            "unambiguous official MODUS match."
        )

    if candidate.resolved_modus_match_id is None:
        raise ValueError(
            "The resolved enrichment candidate has no "
            "official MODUS match ID."
        )

    return candidate


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
            "message": request.query_params.get(
                "message"
            ),
        },
    )


@router.post(
    "/current-enrichment/{internal_match_id}"
)
def enrich_current_match(
    internal_match_id: int,
    db: Session = Depends(get_db),
):
    try:
        # Re-discover on the server immediately before writing.
        # Browser-submitted MODUS IDs or player names are never trusted.
        report = (
            run_current_match_enrichment_discovery()
        )

        candidate = (
            _resolved_candidate_for_match(
                report,
                internal_match_id,
            )
        )

        result = workflow_service.run(
            db,
            candidate,
        )

        return _redirect(
            (
                f"Match #{result.internal_match_id} enriched "
                f"from official MODUS match "
                f"{result.modus_match_id}. "
                f"Import batch #{result.batch_id}."
            )
        )

    except Exception as exc:
        return _redirect(
            (
                f"Match #{internal_match_id} enrichment "
                f"was not completed: {exc}"
            )
        )
