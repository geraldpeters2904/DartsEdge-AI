from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer

from app.db import Base


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)

    # Bankroll Management
    bankroll = Column(Float, default=5000.0)
    default_stake_percent = Column(Float, default=2.0)
    kelly_fraction = Column(Float, default=0.50)
    max_daily_risk = Column(Float, default=10.0)

    # Value Betting
    minimum_edge = Column(Float, default=5.0)
    minimum_confidence = Column(Float, default=60.0)

    # Automation
    auto_refresh = Column(Boolean, default=True)
    refresh_interval = Column(Integer, default=60)  # minutes

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )