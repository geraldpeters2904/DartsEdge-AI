from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.diagnostics_service import build_diagnostics
from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.services.live_edge_monitor_service import (
    live_edge_monitor,
)
from app.services.current_match_enrichment_v33_sparse_consensus_risk_diagnostic_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService,
)
from app.services.current_match_enrichment_v33_dual_low_history_risk_flag_service import (
    CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService,
)
from app.templates_config import templates
from app.version import version_payload

router = APIRouter(tags=["system"])


@router.get("/version")
def version_endpoint():
    return version_payload()


def _monitor_health(
    status,
    *,
    stale_after_seconds: float,
):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    last_run = None

    if status.last_run_at:
        try:
            last_run = datetime.fromisoformat(
                status.last_run_at
            )

            if last_run.tzinfo is None:
                last_run = last_run.replace(
                    tzinfo=timezone.utc
                )
        except ValueError:
            last_run = None

    age_seconds = (
        (now - last_run).total_seconds()
        if last_run is not None
        else None
    )

    started_at = None

    if status.started_at:
        try:
            started_at = datetime.fromisoformat(
                status.started_at
            )

            if started_at.tzinfo is None:
                started_at = started_at.replace(
                    tzinfo=timezone.utc
                )
        except ValueError:
            started_at = None

    started_age_seconds = (
        (now - started_at).total_seconds()
        if started_at is not None
        else None
    )

    never_completed_stale = (
        status.running
        and status.last_run_at is None
        and started_age_seconds is not None
        and started_age_seconds
        > stale_after_seconds
    )

    stale = (
        not status.running
        or never_completed_stale
        or (
            age_seconds is not None
            and age_seconds
            > stale_after_seconds
        )
    )

    return {
        "running": status.running,
        "started_at": status.started_at,
        "last_run_at": status.last_run_at,
        "next_run_at": status.next_run_at,
        "runs": status.runs,
        "failures": status.failures,
        "last_error": status.last_error,
        "age_seconds": (
            round(age_seconds, 3)
            if age_seconds is not None
            else None
        ),
        "started_age_seconds": (
            round(started_age_seconds, 3)
            if started_age_seconds is not None
            else None
        ),
        "stale_after_seconds": stale_after_seconds,
        "stale": stale,
        "healthy": not stale,
    }


@router.get("/health")
def health_endpoint(db: Session = Depends(get_db)):
    diagnostics = build_diagnostics(db)

    forward = _monitor_health(
        forward_schedule_monitor.status(),
        stale_after_seconds=1800.0,
    )

    live_edge = _monitor_health(
        live_edge_monitor.status(),
        stale_after_seconds=600.0,
    )

    monitors_healthy = (
        forward["healthy"]
        and live_edge["healthy"]
    )

    return {
        "status": (
            diagnostics["overall_status"]
            if monitors_healthy
            else "degraded"
        ),
        "version": diagnostics["release"]["version"],
        "build": diagnostics["release"]["build"],
        "checks": diagnostics["checks"],
        "monitors": {
            "forward_schedule": forward,
            "live_edge": live_edge,
        },
    }



@router.get("/diagnostics/sparse-consensus-risk")
def sparse_consensus_risk_endpoint(
    db: Session = Depends(get_db),
):
    window_size = 1000

    recent_ids = (
        CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService
        ._select_match_ids(
            db,
            offset=0,
            limit=1000000,
        )
    )

    total_completed = len(
        recent_ids
    )

    offset = max(
        total_completed - window_size,
        0,
    )

    diagnostic = (
        CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService()
        .analyse(
            db,
            offset=offset,
            window_size=window_size,
            probability_lower=65.0,
            probability_upper=70.0,
            history_threshold=3,
            agreement_threshold=100.0,
            competition_code="MODUS",
        )
    )

    return {
        "model_version": diagnostic.model_version,
        "window_size": diagnostic.window_size,
        "offset": diagnostic.offset,
        "segment_matches": diagnostic.segment_matches,
        "flagged_matches": diagnostic.flagged_matches,
        "density": diagnostic.density,
        "risk_state": diagnostic.risk_state,
        "elevated": diagnostic.elevated,
        "high": diagnostic.high,
        "explanation": diagnostic.explanation,
    }


@router.get("/diagnostics")
def diagnostics_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "diagnostics.html",
        {
            "request": request,
            "diagnostics": build_diagnostics(db),
        },
    )
