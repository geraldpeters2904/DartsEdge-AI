from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.player import Player
from app.templates_config import templates


router = APIRouter()


@router.get("/players")
def players_page(request: Request):
    db = SessionLocal()

    try:
        players = (
            db.query(Player)
            .order_by(Player.name.asc())
            .all()
        )

        return templates.TemplateResponse(
            "players.html",
            {
                "request": request,
                "players": players,
            },
        )

    finally:
        db.close()