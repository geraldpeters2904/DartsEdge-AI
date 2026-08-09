from datetime import datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
)

from app.db import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # Sprint 2 canonical identity.
    fixture_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    bookmaker_code = Column(
        String,
        nullable=True,
        index=True,
    )

    market = Column(
        String,
        nullable=False,
        index=True,
        default="match_winner",
    )

    selection = Column(
        String,
        nullable=False,
        index=True,
    )

    decimal_odds = Column(
        Float,
        nullable=False,
    )

    implied_probability = Column(
        Float,
        nullable=True,
    )

    captured_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    source_reference = Column(
        String,
        nullable=True,
    )

    # Legacy fields retained so the historical odds database remains readable
    # during the Sprint 2 transition.
    fixture_date = Column(
        Date,
        nullable=True,
        index=True,
    )

    tournament = Column(
        String,
        nullable=True,
    )

    player_a = Column(
        String,
        nullable=True,
    )

    player_b = Column(
        String,
        nullable=True,
    )

    bookmaker = Column(
        String,
        nullable=True,
    )

    provider_id = Column(
        String,
        nullable=True,
    )

    external_id = Column(
        String,
        nullable=True,
    )

    fingerprint = Column(
        String,
        nullable=True,
    )
