from sqlalchemy import Column, Integer, String, ForeignKey
from app.db import Base


class MatchPlayerStats(Base):
    __tablename__ = "match_player_stats"

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer, ForeignKey("matches.id"))

    player_name = Column(String)

    one80s = Column(Integer, default=0)