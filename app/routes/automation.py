from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.automation_service import AutomationBusyError, AutomationService
from app.templates_config import templates

router = APIRouter()


@router.get("/automation")
def automation_page(request: Request):
    db = SessionLocal()
    try:
        service = AutomationService(db)
        return templates.TemplateResponse("automation.html", {
            "request": request,
            "jobs": service.definitions(),
            "history": service.latest_runs(),
            "message": request.query_params.get("message"),
            "mode": "manual",
        })
    finally:
        db.close()


@router.post("/automation/run/{job_id}")
def run_automation_job(job_id: str):
    db = SessionLocal()
    try:
        try:
            run = AutomationService(db).run(job_id)
            message = f"{run.job_name}: {run.status}. {run.detail or run.error or ''}"
        except (KeyError, AutomationBusyError) as exc:
            message = str(exc)
        return RedirectResponse(f"/automation?message={message}", status_code=303)
    finally:
        db.close()


@router.get("/api/automation")
def automation_api():
    db = SessionLocal()
    try:
        service = AutomationService(db)
        return {
            "mode": "manual",
            "registered": len(service.jobs),
            "jobs": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "running": row["running"],
                    "last_status": row["last_run"].status if row["last_run"] else None,
                }
                for row in service.definitions()
            ],
        }
    finally:
        db.close()
