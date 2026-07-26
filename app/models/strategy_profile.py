from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.db import Base


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"
    __table_args__ = (UniqueConstraint("strategy_uuid", "version", name="uq_strategy_uuid_version"),)

    id = Column(Integer, primary_key=True, index=True)
    strategy_uuid = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False, default="")
    version = Column(Integer, nullable=False, default=1)
    rules_json = Column(Text, nullable=False, default="{}")
    is_active = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
