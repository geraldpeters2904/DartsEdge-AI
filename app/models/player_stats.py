from sqlalchemy import Column, Integer, Float, ForeignKey
from app.db import Base


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("players.id"))

    matches = Column(Integer, default=0)

    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)

    legs_won = Column(Integer, default=0)
    legs_lost = Column(Integer, default=0)

    first9_average = Column(Float, default=0)

    one80_total = Column(Integer, default=0)

    one80_per_match = Column(Float, default=0)

    checkout100 = Column(Integer, default=0)

    highest_checkout = Column(Integer, default=0)