from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.value_board_service import build_value_board
from app.templates_config import templates


router = APIRouter()


@router.get("/value-board")
def value_board(request: Request):
    db = SessionLocal()

    try:
        rows = build_value_board(db)

        return templates.TemplateResponse(
            "value_board.html",
            {
                "request": request,
                "rows": rows,
            },
        )

    finally:
        db.close()