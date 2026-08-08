from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db import Base


class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True, index=True)

    code = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    priority = Column(
        Integer,
        nullable=False,
        default=100,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
