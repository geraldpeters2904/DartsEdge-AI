from app.routes.importer import router as importer_router
from app.routes.prediction_history import router as prediction_history_router
from app.routes.statistics import router as statistics_router
from app.routes.player_profile import router as player_profile_router
from app.routes.rankings import router as rankings_router
from app.routes.dashboard import router as dashboard_router
from app.routes.predict import router as predict_router
from app.routes.accuracy import router as accuracy_router
from app.routes.update_prediction import router as update_prediction_router
from app.models.prediction import Prediction
from app.services.rating_service import dartsedge_rating
from app.services.first180_service import first_180_market
from app.services.simulation_service import simulate_match
from app.services.match_intelligence_service import compare_players
from app.services.player_profile_service import get_player_profile
import csv
import io
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.db import create_database, SessionLocal
from app.models.player import Player
from app.models.match import Match
from app.models.player_stats import PlayerStats
from app.models.match_player_stats import MatchPlayerStats

from app.services.match_engine import (
    win_probability,
    expected_180s,
    leg_win_probability,
    value_edge
)
from app.services.elo_service import update_elo
from app.services.stats_service import update_player_stats
from app.services.markets_service import one80_markets
from app.services.form_service import weighted_expected_180s


app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
app.include_router(dashboard_router)
app.include_router(update_prediction_router)
create_database()
app.include_router(predict_router)
app.include_router(accuracy_router)
app.include_router(rankings_router)
app.include_router(player_profile_router)
app.include_router(statistics_router)
app.include_router(prediction_history_router)
app.include_router(importer_router)

@app.get("/")
def home():
    return {"status": "DartsEdge AI running"}

@app.get("/match")
def match(player_a: str, player_b: str):
    db = SessionLocal()

    a = db.query(Player).filter(Player.name == player_a).first()
    b = db.query(Player).filter(Player.name == player_b).first()

    if not a or not b:
        db.close()
        return {"error": "Player not found"}

    elo_prob = win_probability(a.elo, b.elo)
    sim_prob = leg_win_probability(a, b)
    final_prob_a = (elo_prob * 0.6) + (sim_prob * 0.4)

    form_180_a = weighted_expected_180s(db, player_a)
    form_180_b = weighted_expected_180s(db, player_b)

    exp_180_a = form_180_a["expected"]
    exp_180_b = form_180_b["expected"]

    value = value_edge(final_prob_a)
    markets_180 = one80_markets(exp_180_a, exp_180_b)

    db.close()

    return {
        "player_a": player_a,
        "player_b": player_b,
        "win_prob_a": round(final_prob_a, 3),
        "win_prob_b": round(1 - final_prob_a, 3),
        "expected_180s_a": round(exp_180_a, 2),
        "expected_180s_b": round(exp_180_b, 2),
        "form_180_a": form_180_a,
        "form_180_b": form_180_b,
        "markets_180": markets_180,
        "value_bet": value
    }
