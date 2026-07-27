from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from app.db import Base


class BetSlipItem(Base):
    __tablename__ = "bet_slip_items"
    __table_args__ = (
        UniqueConstraint("fixture_id", "market", "selection", name="uq_bet_slip_fixture_market_selection"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    market = Column(String, nullable=False, default="Match Winner")
    selection = Column(String, nullable=False)
    bookmaker = Column(String, nullable=False, default="Best available")
    odds = Column(Float, nullable=False)
    stake = Column(Float, nullable=False, default=1.0)
    model_probability = Column(Float, nullable=True)
    expected_value = Column(Float, nullable=True)
    kelly_stake = Column(Float, nullable=True)
    strategy_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
