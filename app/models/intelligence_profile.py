from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db import Base


class IntelligenceProfile(Base):
    __tablename__ = "intelligence_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    description = Column(String, default="")
    weights_json = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
