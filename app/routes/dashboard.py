from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.services.dashboard_service import build_dashboard_data


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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