from __future__ import annotations

from app.db import SessionLocal
from app.services.forward_fixture_catchup_service import (
    run_forward_fixture_catchup,
)


def run_once(
):
    db = SessionLocal()

    try:
        report = run_forward_fixture_catchup(
            db
        )

        db.commit()

        return report

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
