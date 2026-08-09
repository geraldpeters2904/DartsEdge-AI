
from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.prediction_adapter_self_test_service import (
    run_prediction_adapter_self_test,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/prediction-self-test")
def prediction_self_test_page(
    request: Request,
):
    db = SessionLocal()

    try:
        report = run_prediction_adapter_self_test(
            db
        )

        return templates.TemplateResponse(
            "prediction_adapter_self_test.html",
            {
                "request": request,
                "report": report,
            },
        )
    finally:
        db.close()
