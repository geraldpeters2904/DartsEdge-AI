from fastapi import APIRouter, Request
from app.templates_config import templates
from app.db import SessionLocal
from app.models.player import Player
from app.models.player_stats import PlayerStats


router = APIRouter()


@router.get("/statistics")
def statistics_page(request: Request):
    db = SessionLocal()

    try:
        players = db.query(Player).order_by(Player.elo.desc()).all()
        rows = []

        for player in players:
            stats = db.query(PlayerStats).filter(
                PlayerStats.player_id == player.id
            ).first()

            if stats:
                win_pct = (
                    round((stats.wins / stats.matches) * 100, 1)
                    if stats.matches
                    else 0
                )

                rows.append({
                    "name": player.name,
                    "elo": player.elo,
                    "matches": stats.matches,
                    "wins": stats.wins,
                    "losses": stats.losses,
                    "win_pct": win_pct,
                    "legs_won": stats.legs_won,
                    "legs_lost": stats.legs_lost,
                    "one80_per_match": stats.one80_per_match,
                })
            else:
                rows.append({
                    "name": player.name,
                    "elo": player.elo,
                    "matches": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_pct": 0,
                    "legs_won": 0,
                    "legs_lost": 0,
                    "one80_per_match": 0,
                })

        return templates.TemplateResponse(
            "statistics.html",
            {
                "request": request,
                "rows": rows,
            },
        )

    finally:
        db.close()