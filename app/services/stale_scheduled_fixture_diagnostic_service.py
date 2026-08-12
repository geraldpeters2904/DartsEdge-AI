from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.match import Match


@dataclass(frozen=True)
class StaleScheduledFixtureDiagnostic:
    stale_count: int
    healthy: bool
    oldest_date: object
    newest_date: object
    explanation: str


def build_stale_scheduled_fixture_diagnostic(
    db: Session,
    *,
    today: date | None = None,
) -> StaleScheduledFixtureDiagnostic:
    current_day = (
        today
        or date.today()
    )

    rows = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date < current_day,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .all()
    )

    count = len(rows)

    if not rows:
        return StaleScheduledFixtureDiagnostic(
            stale_count=0,
            healthy=True,
            oldest_date=None,
            newest_date=None,
            explanation=(
                "No past fixtures remain marked as scheduled."
            ),
        )

    return StaleScheduledFixtureDiagnostic(
        stale_count=count,
        healthy=False,
        oldest_date=rows[0].date,
        newest_date=rows[-1].date,
        explanation=(
            f"{count} past fixture(s) remain marked as "
            "scheduled and require reconciliation."
        ),
    )
