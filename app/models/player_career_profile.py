from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.db import Base


class PlayerCareerProfile(Base):
    """Materialised career summary derived from player match performances."""

    __tablename__ = "player_career_profiles"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(
        Integer,
        ForeignKey("players.id"),
        nullable=False,
        index=True,
    )
    competition_code = Column(
        String(40),
        nullable=False,
        default="ALL",
        index=True,
    )

    matches_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    win_percentage = Column(Float, nullable=False, default=0.0)

    legs_won = Column(Integer, nullable=False, default=0)
    legs_lost = Column(Integer, nullable=False, default=0)
    leg_difference = Column(Integer, nullable=False, default=0)

    average_three_dart_average = Column(Float, nullable=True)
    average_first_nine_average = Column(Float, nullable=True)

    scores_100_plus = Column(Integer, nullable=False, default=0)
    scores_140_plus = Column(Integer, nullable=False, default=0)
    scores_180 = Column(Integer, nullable=False, default=0)
    maximums_per_match = Column(Float, nullable=False, default=0.0)

    checkout_attempts = Column(Integer, nullable=False, default=0)
    checkouts_completed = Column(Integer, nullable=False, default=0)
    calculated_checkout_percentage = Column(Float, nullable=True)
    average_reported_checkout_percentage = Column(Float, nullable=True)
    highest_checkout = Column(Integer, nullable=True)

    recent_form_json = Column(Text, nullable=False, default="[]")

    first_match_date = Column(Date, nullable=True)
    latest_match_date = Column(Date, nullable=True)

    refreshed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "competition_code",
            name="uq_player_career_profile_scope",
        ),
    )
