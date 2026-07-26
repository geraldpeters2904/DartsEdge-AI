from fastapi import APIRouter, Request
from app.templates_config import templates

from app.db import SessionLocal
from app.services.dashboard_service import build_dashboard_data


router = APIRouter()


@router.get("/dashboard")
def dashboard_page(request: Request):
    db = SessionLocal()

    try:
        dashboard = build_dashboard_data(db)

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                **dashboard,
            },
        )

    finally:
        db.close()