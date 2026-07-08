from app.services.simulation_service import simulate_match
from app.services.match_intelligence_service import compare_players
from app.services.player_profile_service import get_player_profile
import csv
import io
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.templating import Jinja2Templates

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
templates = Jinja2Templates(directory="app/templates")

create_database()


@app.get("/")
def home():
    return {"status": "DartsEdge AI running"}


@app.get("/dashboard")
def dashboard(request: Request):
    db = SessionLocal()

    players = db.query(Player).order_by(Player.elo.desc()).all()
    matches = db.query(Match).order_by(Match.date.desc()).limit(10).all()

    player_count = db.query(Player).count()
    match_count = db.query(Match).count()

    db.close()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "players": players,
            "matches": matches,
            "player_count": player_count,
            "match_count": match_count
        }
    )


@app.get("/players")
def list_players():
    db = SessionLocal()

    players = db.query(Player).all()

    result = []

    for p in players:
        result.append({
            "id": p.id,
            "name": p.name,
            "elo": p.elo,
            "average": p.average,
            "checkout": p.checkout,
            "one80_rate": p.one80_rate
        })

    db.close()

    return result


@app.get("/matches")
def list_matches():
    db = SessionLocal()

    matches = db.query(Match).all()

    result = []

    for m in matches:
        result.append({
            "id": m.id,
            "date": str(m.date),
            "player_a": m.player_a,
            "player_b": m.player_b,
            "winner": m.winner,
            "score": m.score
        })

    db.close()

    return result


@app.get("/match-player-stats")
def list_match_player_stats():
    db = SessionLocal()

    stats = db.query(MatchPlayerStats).all()

    result = []

    for s in stats:
        result.append({
            "id": s.id,
            "match_id": s.match_id,
            "player_name": s.player_name,
            "one80s": s.one80s
        })

    db.close()

    return result


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


@app.get("/predict")
def predict_page(request: Request):
    db = SessionLocal()

    players = db.query(Player).order_by(Player.name.asc()).all()

    db.close()

    return templates.TemplateResponse(
        "predict.html",
        {
            "request": request,
            "players": players
        }
    )


@app.get("/predict-ui")
def predict_ui(request: Request, player_a: str, player_b: str):
    db = SessionLocal()

    players = db.query(Player).order_by(Player.name.asc()).all()

    profile_a = get_player_profile(db, player_a)
    profile_b = get_player_profile(db, player_b)
    intelligence = compare_players(profile_a, profile_b)

    if not profile_a or not profile_b:
        db.close()
        return {"error": "Player not found"}

    a = db.query(Player).filter(Player.name == player_a).first()
    b = db.query(Player).filter(Player.name == player_b).first()

    elo_prob = win_probability(profile_a["elo"], profile_b["elo"])
    sim_prob = leg_win_probability(a, b)
    final_prob_a = (elo_prob * 0.6) + (sim_prob * 0.4)

    exp_180_a = profile_a["form"]["expected"]
    exp_180_b = profile_b["form"]["expected"]

    value = value_edge(final_prob_a)
    markets_180 = one80_markets(exp_180_a, exp_180_b)
    simulation = simulate_match(profile_a, profile_b)

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
            "result": result
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
        player_a = db.query(Player).filter(
            Player.name == row["player_a"]
        ).first()

        player_b = db.query(Player).filter(
            Player.name == row["player_b"]
        ).first()

        if not player_a or not player_b:
            skipped += 1
            continue

        match_date = datetime.strptime(
            row["date"],
            "%Y-%m-%d"
        ).date()

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
            player_a=row["player_a"],
            player_b=row["player_b"],
            winner=row["winner"],
            score=row["score"]
        )

        db.add(match)
        db.flush()

        db.add(
            MatchPlayerStats(
                match_id=match.id,
                player_name=row["player_a"],
                one80s=int(row.get("player_a_180s", 0))
            )
        )

        db.add(
            MatchPlayerStats(
                match_id=match.id,
                player_name=row["player_b"],
                one80s=int(row.get("player_b_180s", 0))
            )
        )

        update_elo(player_a, player_b, row["winner"])

        update_player_stats(
            db,
            player_a,
            player_b,
            row["winner"],
            row["score"]
        )

        imported += 1

    db.commit()
    db.close()

    return {
        "message": "Import complete",
        "imported": imported,
        "skipped": skipped
    }
@app.get("/player-profile/{player_name}")
def player_profile(player_name: str):

    db = SessionLocal()

    profile = get_player_profile(db, player_name)

    db.close()

    if not profile:
        return {"error": "Player not found"}

    return profile