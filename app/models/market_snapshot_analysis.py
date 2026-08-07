from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
)

from app.db import Base


class MarketSnapshotAnalysis(Base):
    __tablename__ = "market_snapshot_analyses"
    __table_args__ = (
        UniqueConstraint(
            "analysis_key",
            name="uq_market_snapshot_analysis_key",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    analysis_key = Column(
        String(64),
        nullable=False,
        index=True,
    )

    fixture_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    tournament = Column(
        String,
        default="Unknown",
        index=True,
    )

    player_a = Column(
        String,
        nullable=False,
        index=True,
    )

    player_b = Column(
        String,
        nullable=False,
        index=True,
    )

    market = Column(
        String,
        default="match_winner",
        index=True,
    )

    selection = Column(
        String,
        nullable=False,
        index=True,
    )

    bookmaker = Column(
        String,
        nullable=False,
        index=True,
    )

    opening_odds = Column(
        Float,
        nullable=False,
    )

    latest_odds = Column(
        Float,
        nullable=False,
    )

    best_odds = Column(
        Float,
        nullable=False,
    )

    closing_odds = Column(
        Float,
        nullable=True,
    )

    movement_percent = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    implied_probability_change_points = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    movement_direction = Column(
        String(30),
        nullable=False,
        default="stable",
        index=True,
    )

    volatility = Column(
        String(30),
        nullable=False,
        default="low",
        index=True,
    )

    update_count = Column(
        Integer,
        nullable=False,
        default=1,
    )

    clv_percent = Column(
        Float,
        nullable=True,
    )

    probability_clv_points = Column(
        Float,
        nullable=True,
    )

    beat_closing_line = Column(
        Integer,
        nullable=True,
    )

    analysed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
