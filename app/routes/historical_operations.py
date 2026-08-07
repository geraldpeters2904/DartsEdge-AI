from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.historical_operations_service import (
    HistoricalOperationsService,
)
from app.services.historical_workflow_worker import (
    historical_workflow_worker,
)
from app.templates_config import templates


router = APIRouter()
historical_operations_service = HistoricalOperationsService()
historical_workflow_service = (
    historical_workflow_worker.workflow_service
)


def _redirect(root: str, message: str):
    return RedirectResponse(
        (
            "/admin/historical-operations?root="
            + quote(root)
            + "&message="
            + quote(message)
        ),
        status_code=303,
    )


@router.get("/admin/historical-operations")
def historical_operations_page(
    request: Request,
    root: str = "",
    db: Session = Depends(get_db),
):
    selected_root = root or str(DEFAULT_CAPTURE_ROOT)

    operations = historical_operations_service.build(
        db,
        root=selected_root,
    )
    workflow = historical_workflow_service.status(
        selected_root,
    )
    worker = historical_workflow_worker.status(
        selected_root,
    )

    return templates.TemplateResponse(
        request,
        "historical_operations.html",
        {
            "operations": operations,
            "workflow": workflow,
            "worker": worker,
            "root": selected_root,
            "message": request.query_params.get("message"),
        },
    )


@router.get("/admin/historical-operations/status")
def historical_operations_status(
    root: str,
):
    workflow = historical_workflow_service.status(root)
    worker = historical_workflow_worker.status(root)

    return {
        "ok": True,
        "workflow_status": workflow.status,
        "runner_status": workflow.runner.status,
        "assistant_running": workflow.assistant.running,
        "current_match_id": workflow.current_match_id,
        "current_destination_folder": (
            workflow.current_destination_folder
        ),
        "processed_matches": (
            workflow.runner.processed_matches
        ),
        "remaining_matches": (
            workflow.runner.remaining_matches
        ),
        "total_matches": workflow.runner.total_matches,
        "runner_message": workflow.runner.last_message,
        "runner_error": workflow.runner.last_error,
        "worker_running": worker.running,
        "worker_iterations": worker.iterations,
        "worker_message": worker.last_message,
        "worker_error": worker.last_error,
    }


@router.post("/admin/historical-operations/workflow/start")
def start_historical_workflow(
    root: str = Form(...),
    watch_folder: str = Form("~/Downloads"),
):
    try:
        status = historical_workflow_service.start(
            root,
            watch_folder=watch_folder,
        )

        if status.running:
            historical_workflow_worker.start(root)

        return _redirect(
            root,
            (
                "Historical workflow and worker started."
                if status.running
                else status.runner.last_message
            ),
        )
    except Exception as exc:
        historical_workflow_worker.stop(root)

        return _redirect(
            root,
            "Could not start historical workflow: " + str(exc),
        )


@router.post("/admin/historical-operations/workflow/pause")
def pause_historical_workflow(
    root: str = Form(...),
):
    try:
        historical_workflow_worker.stop(root)
        historical_workflow_service.pause(root)

        return _redirect(
            root,
            "Historical workflow paused.",
        )
    except Exception as exc:
        return _redirect(
            root,
            "Could not pause historical workflow: " + str(exc),
        )


@router.post("/admin/historical-operations/workflow/resume")
def resume_historical_workflow(
    root: str = Form(...),
    watch_folder: str = Form("~/Downloads"),
):
    try:
        status = historical_workflow_service.resume(
            root,
            watch_folder=watch_folder,
        )

        if status.running:
            historical_workflow_worker.start(root)

        return _redirect(
            root,
            "Historical workflow and worker resumed.",
        )
    except Exception as exc:
        historical_workflow_worker.stop(root)

        return _redirect(
            root,
            "Could not resume historical workflow: " + str(exc),
        )


@router.post("/admin/historical-operations/workflow/stop")
def stop_historical_workflow(
    root: str = Form(...),
):
    try:
        historical_workflow_worker.stop(root)
        historical_workflow_service.stop(root)

        return _redirect(
            root,
            "Historical workflow and worker stopped.",
        )
    except Exception as exc:
        return _redirect(
            root,
            "Could not stop historical workflow: " + str(exc),
        )
