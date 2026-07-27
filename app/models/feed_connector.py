from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db import Base


class FeedConnectorConfig(Base):
    __tablename__ = "feed_connector_configs"

    id = Column(Integer, primary_key=True)
    connector_id = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    connector_type = Column(String(30), nullable=False, default="json")
    feed_url = Column(Text, nullable=True)
    auth_token = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=False)
    competitions_json = Column(Text, nullable=False, default="[]")
    timeout_seconds = Column(Integer, nullable=False, default=15)
    retry_count = Column(Integer, nullable=False, default=2)
    refresh_interval_minutes = Column(Integer, nullable=False, default=60)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class FeedSyncRun(Base):
    __tablename__ = "feed_sync_runs"

    id = Column(Integer, primary_key=True)
    connector_id = Column(String(80), nullable=False, index=True)
    action = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    records_received = Column(Integer, nullable=False, default=0)
    records_new = Column(Integer, nullable=False, default=0)
    records_existing = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
