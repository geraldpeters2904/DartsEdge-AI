from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
)

from app.db import Base


class OpportunitySnapshot(Base):
    __tablename__ = "opportunity_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    fixture_id = Column(Integer, nullable=False, index=True)
    fixture_date = Column(Date, nullable=False, index=True)

    tournament = Column(String, nullable=True)
    player_a = Column(String, nullable=False)
    player_b = Column(String, nullable=False)
    selection = Column(String, nullable=False)
    market = Column(String, nullable=False, default="match_winner")

    bookmaker = Column(String, nullable=True)
    decimal_odds = Column(Float, nullable=True)

    model_probability = Column(Float, nullable=True)
    model_confidence = Column(Float, nullable=True)
    expected_value_percent = Column(Float, nullable=True)
    edge_percent = Column(Float, nullable=True)

    decision_score = Column(Integer, nullable=False)
    decision_grade = Column(String, nullable=False)
    recommendation = Column(String, nullable=False)

    consensus_score = Column(Float, nullable=True)
    steam_direction = Column(String, nullable=True)
    steam_strength = Column(String, nullable=True)
    coordinated_move = Column(Boolean, nullable=False, default=False)

    lifecycle_state = Column(String, nullable=False, default="NEW")

    suggested_stake = Column(Float, nullable=False, default=0.0)

    captured_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
