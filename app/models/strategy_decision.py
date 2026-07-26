from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db import Base


class StrategyDecision(Base):
    __tablename__ = "strategy_decisions"

    id = Column(Integer, primary_key=True, index=True)
    decision_uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    strategy_uuid = Column(String(36), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False, index=True)
    strategy_version = Column(Integer, nullable=False)
    enforcement_mode = Column(String(20), nullable=False, default="shadow")
    trading_mode = Column(String(20), nullable=False, default="live")

    competition = Column(String(200), nullable=False, default="", index=True)
    market = Column(String(100), nullable=False, default="match_winner", index=True)
    bookmaker = Column(String(120), nullable=False, default="")
    model_probability = Column(Float, nullable=False)
    confidence_percent = Column(Float, nullable=False)
    decimal_odds = Column(Float, nullable=False)
    edge_percent = Column(Float, nullable=False)
    expected_value_percent = Column(Float, nullable=False)

    official_decision = Column(String(30), nullable=False)
    official_stake = Column(Float, nullable=False, default=0.0)
    strategy_decision = Column(String(30), nullable=False)
    strategy_stake = Column(Float, nullable=False, default=0.0)
    effective_decision = Column(String(30), nullable=False)
    effective_stake = Column(Float, nullable=False, default=0.0)
    blockers_json = Column(Text, nullable=False, default="[]")
    warnings_json = Column(Text, nullable=False, default="[]")

    outcome = Column(String(20), nullable=True)
    profit_loss = Column(Float, nullable=True)
    settled_at = Column(DateTime, nullable=True)
