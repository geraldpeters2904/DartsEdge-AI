from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.diagnostics_service import build_diagnostics
from app.templates_config import templates
from app.version import version_payload

router = APIRouter(tags=["system"])


@router.get("/version")
def version_endpoint():
    return version_payload()


@router.get("/health")
def health_endpoint(db: Session = Depends(get_db)):
    diagnostics = build_diagnostics(db)
    return {
        "status": diagnostics["overall_status"],
        "version": diagnostics["release"]["version"],
        "build": diagnostics["release"]["build"],
        "checks": diagnostics["checks"],
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
