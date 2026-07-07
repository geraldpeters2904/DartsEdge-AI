from app.db import SessionLocal
from app.models.player import Player

players = [
    {"name": "lewis_pride", "elo": 1600, "average": 92, "checkout": 38, "one80_rate": 1.1},
    {"name": "scott_taylor", "elo": 1580, "average": 90, "checkout": 36, "one80_rate": 0.9},
    {"name": "carl_wilson", "elo": 1625, "average": 93, "checkout": 40, "one80_rate": 1.2},
    {"name": "adrian_gray", "elo": 1575, "average": 88, "checkout": 37, "one80_rate": 0.8},
    {"name": "meinte_hibma", "elo": 1550, "average": 86, "checkout": 35, "one80_rate": 0.7},
    {"name": "devon_peterson", "elo": 1560, "average": 87, "checkout": 36, "one80_rate": 0.75},
]

db = SessionLocal()

for p in players:
    existing = db.query(Player).filter(Player.name == p["name"]).first()
    if not existing:
        db.add(Player(**p))

db.commit()
db.close()

print("Players added")