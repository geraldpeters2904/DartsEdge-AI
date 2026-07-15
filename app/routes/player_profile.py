from fastapi import APIRouter, Request
from app.templates_config import templates
from app.db import SessionLocal
from app.services.player_profile_service import get_player_profile


router = APIRouter()


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