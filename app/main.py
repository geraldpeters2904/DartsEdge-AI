import csv
import io
from fastapi import UploadFile, File
from datetime import datetime
from app.models.match import Match
from app.services.elo_service import update_elo
from app.services.stats_service import update_player_stats
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.models.match import Match
from app.db import create_database, SessionLocal
from fastapi import FastAPI
from app.services.players import players
from app.models.player import Player
from app.services.match_engine import (
    win_probability,
    expected_180s,
    leg_win_probability,
    value_edge
)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
create_database()
@app.get("/")
def home():
    return {"status": "DartsEdge AI v2 running"}

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

    exp_180_a = expected_180s(a)
    exp_180_b = expected_180s(b)

    value = value_edge(final_prob_a)

    db.close()

    return {
        "player_a": player_a,
        "player_b": player_b,
        "win_prob_a": round(final_prob_a, 3),
        "win_prob_b": round(1 - final_prob_a, 3),
        "expected_180s_a": round(exp_180_a, 2),
        "expected_180s_b": round(exp_180_b, 2),
        "value_bet": value
    }

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

    from app.models.match import Match

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

    a = db.query(Player).filter(Player.name == player_a).first()
    b = db.query(Player).filter(Player.name == player_b).first()
    players = db.query(Player).order_by(Player.name.asc()).all()

    if not a or not b:
        db.close()
        return {"error": "Player not found"}

    elo_prob = win_probability(a.elo, b.elo)
    sim_prob = leg_win_probability(a, b)

    final_prob_a = (elo_prob * 0.6) + (sim_prob * 0.4)

    exp_180_a = expected_180s(a)
    exp_180_b = expected_180s(b)

    value = value_edge(final_prob_a)

    result = {
        "player_a": player_a,
        "player_b": player_b,
        "win_prob_a": round(final_prob_a, 3),
        "win_prob_b": round(1 - final_prob_a, 3),
        "expected_180s_a": round(exp_180_a, 2),
        "expected_180s_b": round(exp_180_b, 2),
        "value_bet": value
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