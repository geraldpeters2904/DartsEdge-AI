from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint

from app.db import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_odds_snapshot_fingerprint"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fixture_date = Column(Date, nullable=False, index=True)
    tournament = Column(String, default="Unknown")
    player_a = Column(String, nullable=False, index=True)
    player_b = Column(String, nullable=False, index=True)
    market = Column(String, default="match_winner", index=True)
    selection = Column(String, nullable=False, index=True)
    bookmaker = Column(String, nullable=False, index=True)
    decimal_odds = Column(Float, nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    provider_id = Column(String, default="manual-odds")
    external_id = Column(String, nullable=True)
    fingerprint = Column(String, nullable=False)
