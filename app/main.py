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
