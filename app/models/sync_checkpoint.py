from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)

from app.db import Base


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    last_success_at = Column(
        DateTime,
        nullable=True,
    )

    last_message = Column(
        String,
        nullable=True,
    )

    last_error = Column(
        String,
        nullable=True,
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
