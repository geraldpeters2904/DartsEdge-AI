from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db import Base


class AutomationJobRun(Base):
    __tablename__ = "automation_job_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(80), nullable=False, index=True)
    job_name = Column(String(160), nullable=False)
    status = Column(String(20), nullable=False, default="running", index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    records_processed = Column(Integer, nullable=False, default=0)
    detail = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    trigger = Column(String(20), nullable=False, default="manual")
