from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from app.db import Base


class CaptureIterationHistory(Base):
    __tablename__ = "capture_iteration_history"

    id = Column(Integer, primary_key=True, index=True)

    capture_root = Column(
        String(500),
        nullable=False,
        index=True,
    )
    provider = Column(
        String(40),
        nullable=False,
        index=True,
    )
    match_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        index=True,
    )

    started_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    finished_at = Column(
        DateTime,
        nullable=True,
    )
    duration_seconds = Column(
        Float,
        nullable=True,
    )

    matches_captured = Column(
        Integer,
        nullable=False,
        default=0,
    )
    bytes_written = Column(
        Integer,
        nullable=False,
        default=0,
    )
    captures_waiting = Column(
        Integer,
        nullable=False,
        default=0,
    )
    retries_attempted = Column(
        Integer,
        nullable=False,
        default=0,
    )
    warnings = Column(
        Integer,
        nullable=False,
        default=0,
    )
    errors = Column(
        Integer,
        nullable=False,
        default=0,
    )

    error_detail = Column(
        Text,
        nullable=True,
    )
