from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.data_quality_service import get_data_quality

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/data-quality")
def data_quality(
    request: Request,
    db: Session = Depends(get_db),
):

    stats = get_data_quality(db)

    return templates.TemplateResponse(
        "data_quality.html",
        {
            "request": request,
            "stats": stats,
        },
    )