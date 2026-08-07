from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.daily_decision_board_service import (
    build_daily_decision_board,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/decision-board")
def decision_board_page(
    request: Request,
):
    db = SessionLocal()

    try:
        payload = (
            build_daily_decision_board(
                db
            )
        )

        return (
            templates.TemplateResponse(
                "decision_board.html",
                {
                    "request": request,
                    **payload,
                },
            )
        )
    finally:
        db.close()
