from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.db import Base


class PredictionAuditOutcome(Base):
    """Append-only outcome event linked to an immutable prediction audit."""

    __tablename__ = "prediction_audit_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    audit_id = Column(Integer, ForeignKey("prediction_audits.id"), nullable=False, index=True)
    actual_winner = Column(String(200), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="manual")
