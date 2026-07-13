from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.services.player_profile_service import get_player_profile


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/player-profile/{player_name}")
def player_profile_page(request: Request, player_name: str):
    db = SessionLocal()

    try:
        profile = get_player_profile(db, player_name)

        if not profile:
            return {"error": "Player not found"}

        return templates.TemplateResponse(
            "player_profile.html",
            {
                "request": request,
                "profile": profile,
            },
        )

    finally:
        db.close()