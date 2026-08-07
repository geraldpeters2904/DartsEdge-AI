from __future__ import annotations

from app.db import SessionLocal
from app.services.automatic_settlement_pipeline_service import (
    run_automatic_settlement,
)
from app.services.sync_checkpoint_service import (
    mark_failure,
    mark_success,
)


CHECKPOINT_NAME = (
    "automatic-settlement"
)


def run_settlement_sync_once():
    db = SessionLocal()

    try:
        try:
            report = (
                run_automatic_settlement(
                    db,
                    source=(
                        "unified-sync"
                    ),
                )
            )

            mark_success(
                db,
                name=(
                    CHECKPOINT_NAME
                ),
                message=(
                    report.message
                ),
            )

            return report

        except Exception as exc:
            mark_failure(
                db,
                name=(
                    CHECKPOINT_NAME
                ),
                error=str(
                    exc
                ),
            )
            raise

    finally:
        db.close()
