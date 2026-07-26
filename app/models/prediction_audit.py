from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.db import Base


class PredictionAudit(Base):
    """Immutable snapshot of a prediction at the moment it was generated."""

    __tablename__ = "prediction_audits"

    id = Column(Integer, primary_key=True, index=True)
    audit_uuid = Column(String(36), unique=True, nullable=False, index=True)
    prediction_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    source = Column(String(50), nullable=False, default="prediction-centre")
    tournament = Column(String(200), nullable=True, index=True)
    player_a = Column(String(200), nullable=False, index=True)
    player_b = Column(String(200), nullable=False, index=True)
    official_selection = Column(String(200), nullable=False, index=True)
    official_probability = Column(Float, nullable=False)
    legacy_probability_a = Column(Float, nullable=False)
    intelligence_probability_a = Column(Float, nullable=True)

    prediction_confidence = Column(String(30), nullable=True)
    explanation_confidence = Column(String(30), nullable=True)
    profile_name = Column(String(120), nullable=True, index=True)
    profile_version = Column(Integer, nullable=True)
    model_version = Column(String(50), nullable=False)
    application_version = Column(String(50), nullable=False)
    shadow_mode = Column(Boolean, nullable=False, default=True)

    intelligence_rating_a = Column(Float, nullable=True)
    intelligence_rating_b = Column(Float, nullable=True)
    snapshot_json = Column(Text, nullable=False)
