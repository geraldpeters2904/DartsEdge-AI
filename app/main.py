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
app.include_router(update_prediction_router)
create_database()

app.include_router(accuracy_router)

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


@app.get("/predict-ui")
def predict_ui(request: Request, player_a: str, player_b: str):
    db = SessionLocal()

    players = [
        {"name": p.name}
        for p in db.query(Player).order_by(Player.name.asc()).all()
    ]

    profile_a = get_player_profile(db, player_a)
    profile_b = get_player_profile(db, player_b)

    if not profile_a or not profile_b:
        db.close()
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
        first_180_b=first_180["player_b"]
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
        "simulation": simulation
    }

    db.close()

    return templates.TemplateResponse(
        "predict.html",
        {
            "request": request,
            "players": players,
            "result": result,
            "selected_player_a": player_a,
            "selected_player_b": player_b
        }
    )


@app.get("/statistics")
def statistics_page(request: Request):
    db = SessionLocal()

    players = db.query(Player).order_by(Player.elo.desc()).all()

    rows = []

    for p in players:
        stats = db.query(PlayerStats).filter(
            PlayerStats.player_id == p.id
        ).first()

        if stats:
            win_pct = round((stats.wins / stats.matches) * 100, 1) if stats.matches else 0

            rows.append({
                "name": p.name,
                "elo": p.elo,
                "matches": stats.matches,
                "wins": stats.wins,
                "losses": stats.losses,
                "win_pct": win_pct,
                "legs_won": stats.legs_won,
                "legs_lost": stats.legs_lost,
                "one80_per_match": stats.one80_per_match
            })
        else:
            rows.append({
                "name": p.name,
                "elo": p.elo,
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "win_pct": 0,
                "legs_won": 0,
                "legs_lost": 0,
                "one80_per_match": 0
            })

    db.close()

    return templates.TemplateResponse(
        "statistics.html",
        {
            "request": request,
            "rows": rows
        }
    )


@app.get("/import")
def import_page(request: Request):
    return templates.TemplateResponse(
        "import.html",
        {"request": request}
    )


@app.post("/import-matches")
async def import_matches(file: UploadFile = File(...)):
    contents = await file.read()
    decoded = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    db = SessionLocal()
    imported = 0
    skipped = 0

    for row in reader:
        player_a = db.query(Player).filter(Player.name == row["player_a"]).first()
        player_b = db.query(Player).filter(Player.name == row["player_b"]).first()

        if not player_a or not player_b:
            skipped += 1
            continue

        match_date = datetime.strptime(row["date"], "%Y-%m-%d").date()

        existing_match = db.query(Match).filter(
            Match.date == match_date,
            Match.player_a == row["player_a"],
            Match.player_b == row["player_b"],
            Match.winner == row["winner"],
            Match.score == row["score"]
        ).first()

        if existing_match:
            skipped += 1
            continue

        match = Match(
            date=match_date,
            tournament=row.get("tournament", "MODUS"),
            stage=row.get("stage", "Group"),
            match_format=row.get("match_format", "Best of 7"),
            player_a=row["player_a"],
            player_b=row["player_b"],
            winner=row["winner"],
            score=row["score"],
            first_180_player=row.get("first_180_player"),
            first_leg_winner=row.get("first_leg_winner")
        )

        db.add(match)
        db.flush()

        db.add(MatchPlayerStats(
            match_id=match.id,
            player_name=row["player_a"],
            one80s=int(row.get("player_a_180s", 0)),
            average=float(row.get("player_a_average", 0)),
            checkout=float(row.get("player_a_checkout", 0)),
            first9_average=float(row.get("player_a_first9", 0)),
            highest_checkout=int(row.get("player_a_highest_checkout", 0))
        ))

        db.add(MatchPlayerStats(
            match_id=match.id,
            player_name=row["player_b"],
            one80s=int(row.get("player_b_180s", 0)),
            average=float(row.get("player_b_average", 0)),
            checkout=float(row.get("player_b_checkout", 0)),
            first9_average=float(row.get("player_b_first9", 0)),
            highest_checkout=int(row.get("player_b_highest_checkout", 0))
        ))

        update_elo(player_a, player_b, row["winner"])
        update_player_stats(db, player_a, player_b, row["winner"], row["score"])

        imported += 1

    db.commit()
    db.close()

    return {
        "message": "Import complete",
        "imported": imported,
        "skipped": skipped
    }

@app.get("/player-profile/{player_name}")
def player_profile_page(request: Request, player_name: str):

    db = SessionLocal()

    profile = get_player_profile(db, player_name)

    db.close()

    if not profile:
        return {"error": "Player not found"}

    return templates.TemplateResponse(
        "player_profile.html",
        {
            "request": request,
            "profile": profile
        }
    )