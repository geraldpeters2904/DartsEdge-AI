from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.player import Player
from app.services.player_intelligence_service import build_player_intelligence, list_profiles
from app.templates_config import templates

router = APIRouter()


@router.get("/player-intelligence")
def player_intelligence_page(request: Request, player: str = "", db: Session = Depends(get_db)):
    players = db.query(Player).order_by(Player.name.asc()).all()
    profiles = list(list_profiles(db))
    result = build_player_intelligence(db, player) if player else None
    return templates.TemplateResponse("player_intelligence.html", {"request": request, "players": players, "profiles": profiles, "selected_player": player, "result": result})
