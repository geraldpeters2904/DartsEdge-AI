import csv
from datetime import datetime

from app.db import SessionLocal
from app.models.match import Match


db = SessionLocal()

with open("data/sample_matches.csv", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        match = Match(
            date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
            player_a=row["player_a"],
            player_b=row["player_b"],
            winner=row["winner"],
            score=row["score"]
        )

        db.add(match)

db.commit()
db.close()

print("Matches imported")