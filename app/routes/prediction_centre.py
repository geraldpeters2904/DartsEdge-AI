from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.prediction_centre_service import build_prediction_centre
from app.templates_config import templates

router = APIRouter()


@router.get("/prediction-centre")
def prediction_centre_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            "prediction_centre.html",
            {"request": request, **build_prediction_centre(db)},
        )
    finally:
        db.close()
