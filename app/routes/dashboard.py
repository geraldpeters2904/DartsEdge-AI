from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.match import Match
from app.models.player import Player


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard")
def dashboard_page(request: Request):
    db = SessionLocal()

    try:
        player_count = db.query(Player).count()
        match_count = db.query(Match).count()

        players = [
            {
                "name": player.name,
                "elo": player.elo,
                "average": player.average,
                "checkout": player.checkout,
                "one80_rate": getattr(player, "one80_rate", 0),
            }
            for player in (
                db.query(Player)
                .order_by(Player.elo.desc())
                .limit(5)
                .all()
            )
        ]

        matches = [
            {
                "date": match.date,
                "player_a": match.player_a,
                "player_b": match.player_b,
                "winner": match.winner,
                "score": match.score,
            }
            for match in (
                db.query(Match)
                .order_by(Match.date.desc())
                .limit(10)
                .all()
            )
        ]

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "player_count": player_count,
                "match_count": match_count,
                "players": players,
                "matches": matches,
            },
        )

    finally:
        db.close()