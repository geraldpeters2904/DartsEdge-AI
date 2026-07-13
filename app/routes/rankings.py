from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.player import Player
from app.services.player_profile_service import get_player_profile


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/rankings")
def rankings_page(request: Request):
    db = SessionLocal()

    try:
        players = db.query(Player).order_by(Player.name.asc()).all()

        rankings = []

        for player in players:
            profile = get_player_profile(db, player.name)

            if profile:
                rankings.append(profile)

        rankings.sort(
            key=lambda profile: profile["dartsedge_rating"],
            reverse=True,
        )

        return templates.TemplateResponse(
            "rankings.html",
            {
                "request": request,
                "rankings": rankings,
            },
        )

    finally:
        db.close()