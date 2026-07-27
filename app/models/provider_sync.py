from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db import Base


class ProviderSyncRun(Base):
    __tablename__ = "provider_sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(String(80), nullable=False, index=True)
    operation = Column(String(40), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running", index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    records_received = Column(Integer, nullable=False, default=0)
    records_accepted = Column(Integer, nullable=False, default=0)
    error_detail = Column(Text, nullable=True)
