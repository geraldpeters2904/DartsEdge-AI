from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.sync_checkpoint import (
    SyncCheckpoint,
)


def get_checkpoint(
    db: Session,
    name: str,
) -> Optional[
    SyncCheckpoint
]:
    return (
        db.query(
            SyncCheckpoint
        )
        .filter(
            SyncCheckpoint.name
            == name
        )
        .first()
    )


def mark_success(
    db: Session,
    *,
    name: str,
    message: str,
) -> SyncCheckpoint:
    row = get_checkpoint(
        db,
        name,
    )

    if row is None:
        row = SyncCheckpoint(
            name=name,
        )
        db.add(
            row
        )

    now = datetime.utcnow()

    row.last_success_at = now
    row.last_message = message
    row.last_error = None
    row.updated_at = now

    db.commit()
    db.refresh(
        row
    )

    return row


def mark_failure(
    db: Session,
    *,
    name: str,
    error: str,
) -> SyncCheckpoint:
    row = get_checkpoint(
        db,
        name,
    )

    if row is None:
        row = SyncCheckpoint(
            name=name,
        )
        db.add(
            row
        )

    row.last_message = (
        "Sync failed."
    )
    row.last_error = str(
        error
    )
    row.updated_at = (
        datetime.utcnow()
    )

    db.commit()
    db.refresh(
        row
    )

    return row
