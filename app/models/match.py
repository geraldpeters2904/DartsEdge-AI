from sqlalchemy import Column, Integer, String, Date
from app.db import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    date = Column(Date)

    tournament = Column(String, default="MODUS")
    stage = Column(String, default="Group")
    match_format = Column(String, default="Best of 7")

    player_a = Column(String)
    player_b = Column(String)

    winner = Column(String)
    score = Column(String)

    first_180_player = Column(String, nullable=True)
    first_leg_winner = Column(String, nullable=True)