from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.db import Base


class OpportunityIdentity(Base):
    __tablename__ = "opportunity_identities"

    id = Column(Integer, primary_key=True, index=True)

    opportunity_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    fixture_id = Column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
