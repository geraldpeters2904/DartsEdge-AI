
from fastapi import APIRouter, Request

from app.services.prediction_adapter_diagnostic_service import (
    diagnose_prediction_adapter,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/prediction-adapter")
def prediction_adapter_page(
    request: Request,
):
    diagnostic = (
        diagnose_prediction_adapter()
    )

    return templates.TemplateResponse(
        "prediction_adapter_diagnostic.html",
        {
            "request": request,
            "diagnostic": diagnostic,
        },
    )
