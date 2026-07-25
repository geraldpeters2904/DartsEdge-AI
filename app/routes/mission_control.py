from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.mission_control_service import build_mission_control_data
from app.templates_config import templates


router = APIRouter()


@router.get("/mission-control")
def mission_control_page(request: Request):
    db = SessionLocal()

    try:
        mission_control = build_mission_control_data(db)

        return templates.TemplateResponse(
            "mission_control.html",
            {
                "request": request,
                **mission_control,
            },
        )
    finally:
        db.close()
