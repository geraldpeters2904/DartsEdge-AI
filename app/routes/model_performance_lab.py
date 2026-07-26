from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.model_performance_lab_service import build_model_performance_lab
from app.templates_config import templates

router = APIRouter()


@router.get('/model-performance-lab')
def model_performance_lab_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse('model_performance_lab.html', {
            'request': request,
            'lab': build_model_performance_lab(db),
        })
    finally:
        db.close()
