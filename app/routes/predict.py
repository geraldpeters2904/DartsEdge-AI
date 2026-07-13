from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.player import Player
from app.models.prediction import Prediction
from app.services.first180_service import first_180_market
from app.services.markets_service import one80_markets
from app.services.match_engine import (
    leg_win_probability,
    value_edge,
    win_probability,
)
from app.services.match_intelligence_service import compare_players
from app.services.player_profile_service import get_player_profile
from app.services.simulation_service import simulate_match


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/predict")
def predict_page(request: Request):
    db = SessionLocal()

    players = [
        {"name": player.name}
        for player in db.query(Player).order_by(Player.name.asc()).all()
    ]

    db.close()

    return templates.TemplateResponse(
        "predict.html",
        {
            "request": request,
            "players": players,
            "selected_player_a": None,
            "selected_player_b": None,
        },
    )


@router.get("/predict-ui")
def predict_ui(request: Request, player_a: str, player_b: str):
    if player_a == player_b:
        db = SessionLocal()

        players = [
            {"name": player.name}
            for player in db.query(Player).order_by(Player.name.asc()).all()
        ]

        db.close()

        return templates.TemplateResponse(
            "predict.html",
            {
                "request": request,
                "players": players,
                "selected_player_a": player_a,
                "selected_player_b": player_b,
                "error": "Please select two different players.",
            },
            status_code=400,
        )

    db = SessionLocal()

    try:
        players = [
            {"name": player.name}
            for player in db.query(Player).order_by(Player.name.asc()).all()
        ]

        profile_a = get_player_profile(db, player_a)
        profile_b = get_player_profile(db, player_b)

        if not profile_a or not profile_b:
            return {"error": "Player not found"}

        a = db.query(Player).filter(Player.name == player_a).first()
        b = db.query(Player).filter(Player.name == player_b).first()

        intelligence = compare_players(profile_a, profile_b)

        elo_prob = win_probability(profile_a["elo"], profile_b["elo"])
        sim_prob = leg_win_probability(a, b)
        final_prob_a = (elo_prob * 0.6) + (sim_prob * 0.4)

        exp_180_a = profile_a["form"]["expected"]
        exp_180_b = profile_b["form"]["expected"]

        value = value_edge(final_prob_a)
        markets_180 = one80_markets(exp_180_a, exp_180_b)
        first_180 = first_180_market(db, player_a, player_b)
        simulation = simulate_match(profile_a, profile_b)

        predicted_winner = player_a if final_prob_a >= 0.5 else player_b

        prediction = Prediction(
            player_a=player_a,
            player_b=player_b,
            predicted_winner=predicted_winner,
            win_prob_a=round(final_prob_a, 3),
            win_prob_b=round(1 - final_prob_a, 3),
            confidence=intelligence["confidence"],
            rating_a=profile_a["dartsedge_rating"],
            rating_b=profile_b["dartsedge_rating"],
            first_180_a=first_180["player_a"],
            first_180_b=first_180["player_b"],
        )

        db.add(prediction)
        db.commit()

        result = {
            "player_a": player_a,
            "player_b": player_b,
            "win_prob_a": round(final_prob_a, 3),
            "win_prob_b": round(1 - final_prob_a, 3),
            "expected_180s_a": round(exp_180_a, 2),
            "expected_180s_b": round(exp_180_b, 2),
            "form_180_a": profile_a["form"],
            "form_180_b": profile_b["form"],
            "markets_180": markets_180,
            "first_180": first_180,
            "value_bet": value,
            "profile_a": profile_a,
            "profile_b": profile_b,
            "intelligence": intelligence,
            "simulation": simulation,
        }

        return templates.TemplateResponse(
            "predict.html",
            {
                "request": request,
                "players": players,
                "result": result,
                "selected_player_a": player_a,
                "selected_player_b": player_b,
            },
        )

    finally:
        db.close()