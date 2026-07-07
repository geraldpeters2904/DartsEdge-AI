import csv
from datetime import datetime
from app.services.stats_service import update_player_stats
from app.db import SessionLocal
from app.models.match import Match
from app.models.player import Player
from app.services.elo_service import update_elo


db = SessionLocal()

with open("data/sample_matches.csv", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        player_a = db.query(Player).filter(Player.name == row["player_a"]).first()
        player_b = db.query(Player).filter(Player.name == row["player_b"]).first()

        if not player_a or not player_b:
            print(f"Skipping match, player not found: {row}")
            continue

        match = Match(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
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
db.commit()
db.close()

print("Matches imported and Elo ratings updated")