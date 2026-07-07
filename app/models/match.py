from sqlalchemy import Column, Integer, String, Date
from app.db import Base


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    date = Column(Date)

    player_a = Column(String)

    player_b = Column(String)

    winner = Column(String)

    score = Column(String)