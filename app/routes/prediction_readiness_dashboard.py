
from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.prediction_readiness_dashboard_service import (
    build_prediction_readiness_dashboard,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/prediction-readiness")
def prediction_readiness_page(
    request: Request,
):
    db = SessionLocal()

    try:
        dashboard = (
            build_prediction_readiness_dashboard(
                db
            )
        )

        return templates.TemplateResponse(
            "prediction_readiness_dashboard.html",
            {
                "request": request,
                "dashboard": dashboard,
            },
        )

    finally:
        db.close()
