from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.db import Base


class MatchPlayerStats(Base):
    __tablename__ = "match_player_stats"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))

    player_name = Column(String)

    one80s = Column(Integer, default=0)

    average = Column(Float, default=0)
    checkout = Column(Float, default=0)
    first9_average = Column(Float, default=0)
    highest_checkout = Column(Integer, default=0)