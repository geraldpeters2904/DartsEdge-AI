from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
)

from app.db import Base


class OddsMovement(Base):
    __tablename__ = "odds_movements"

    id = Column(Integer, primary_key=True, index=True)

    fixture_id = Column(
        Integer,
        nullable=False,
        index=True,
    )

    bookmaker_code = Column(
        String,
        nullable=False,
        index=True,
    )

    market = Column(
        String,
        nullable=False,
        index=True,
    )

    selection = Column(
        String,
        nullable=False,
        index=True,
    )

    previous_odds = Column(
        Float,
        nullable=False,
    )

    new_odds = Column(
        Float,
        nullable=False,
    )

    absolute_change = Column(
        Float,
        nullable=False,
    )

    percentage_change = Column(
        Float,
        nullable=False,
    )

    direction = Column(
        String,
        nullable=False,
    )

    detected_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
