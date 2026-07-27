from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.db import Base


class PlayerMatchPerformance(Base):
    """
    One immutable set of observed statistics for one player in one match.

    Derived values such as rolling form, momentum and confidence do not belong
    in this table. They will be calculated later by the feature layer.
    """

    __tablename__ = "player_match_performances"

    id = Column(Integer, primary_key=True, index=True)

    match_id = Column(
        Integer,
        ForeignKey("matches.id"),
        nullable=False,
        index=True,
    )
    player_id = Column(
        Integer,
        ForeignKey("players.id"),
        nullable=False,
        index=True,
    )
    opponent_id = Column(
        Integer,
        ForeignKey("players.id"),
        nullable=True,
        index=True,
    )

    competition_code = Column(String(40), nullable=True, index=True)
    player_external_id = Column(String(160), nullable=True, index=True)

    won_match = Column(Boolean, nullable=True)
    threw_first = Column(Boolean, nullable=True)

    legs_won = Column(Integer, nullable=True)
    legs_lost = Column(Integer, nullable=True)
    legs_held = Column(Integer, nullable=True)
    legs_broken = Column(Integer, nullable=True)

    three_dart_average = Column(Float, nullable=True)
    first_nine_average = Column(Float, nullable=True)

    scores_100_plus = Column(Integer, nullable=True)
    scores_140_plus = Column(Integer, nullable=True)
    scores_180 = Column(Integer, nullable=True)

    checkout_attempts = Column(Integer, nullable=True)
    checkouts_completed = Column(Integer, nullable=True)
    checkout_percentage = Column(Float, nullable=True)
    highest_checkout = Column(Integer, nullable=True)

    match_duration_seconds = Column(Integer, nullable=True)

    source_provider = Column(String(64), nullable=False, index=True)
    source_external_id = Column(String(160), nullable=True)
    source_confidence = Column(
        String(24),
        default="reported",
        nullable=False,
    )

    observed_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "player_id",
            name="uq_player_match_performance",
        ),
        Index(
            "ix_player_match_performance_player_created",
            "player_id",
            "created_at",
        ),
        Index(
            "ix_player_match_performance_competition_player",
            "competition_code",
            "player_id",
        ),
    )