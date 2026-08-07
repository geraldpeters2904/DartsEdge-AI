from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.match import Match


@dataclass(frozen=True)
class FixtureLifecycleRecord:
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    stage: Optional[str] = None
    match_format: Optional[str] = None
    status: str = "scheduled"
    winner: Optional[str] = None
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    provider_id: Optional[str] = None


@dataclass(frozen=True)
class FixtureSyncReport:
    scanned: int
    created: int
    updated: int
    completed: int
    unchanged: int
    skipped: int
    window_start: date
    window_end: date
    message: str


def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _fixture_matches(
    row: Match,
    record: FixtureLifecycleRecord,
) -> bool:
    return (
        row.date == record.fixture_date
        and _normalise(row.player_a)
        == _normalise(record.player_a)
        and _normalise(row.player_b)
        == _normalise(record.player_b)
    )


def _find_existing(
    db: Session,
    record: FixtureLifecycleRecord,
) -> Optional[Match]:
    rows = (
        db.query(Match)
        .filter(
            Match.date
            == record.fixture_date
        )
        .all()
    )

    for row in rows:
        if _fixture_matches(
            row,
            record,
        ):
            return row

    return None


def _apply_record(
    row: Match,
    record: FixtureLifecycleRecord,
) -> bool:
    changed = False

    values = {
        "tournament": (
            record.tournament
            or row.tournament
        ),
        "stage": (
            record.stage
            if record.stage is not None
            else getattr(
                row,
                "stage",
                None,
            )
        ),
        "match_format": (
            record.match_format
            if record.match_format is not None
            else getattr(
                row,
                "match_format",
                None,
            )
        ),
        "status": (
            record.status
            or getattr(
                row,
                "status",
                "scheduled",
            )
        ),
    }

    for field, value in values.items():
        if (
            hasattr(
                row,
                field,
            )
            and getattr(
                row,
                field,
            ) != value
        ):
            setattr(
                row,
                field,
                value,
            )
            changed = True

    optional_fields = {
        "winner": (
            record.winner
        ),
        "score_a": (
            record.score_a
        ),
        "score_b": (
            record.score_b
        ),
        "provider_id": (
            record.provider_id
        ),
    }

    for field, value in optional_fields.items():
        if (
            value is not None
            and hasattr(
                row,
                field,
            )
            and getattr(
                row,
                field,
                None,
            ) != value
        ):
            setattr(
                row,
                field,
                value,
            )
            changed = True

    return changed


def synchronise_fixture_records(
    db: Session,
    records: Iterable[
        FixtureLifecycleRecord
    ],
    *,
    window_start: date,
    window_end: date,
) -> FixtureSyncReport:
    created = 0
    updated = 0
    completed = 0
    unchanged = 0
    skipped = 0

    records = list(
        records
    )

    for record in records:
        if (
            record.fixture_date
            < window_start
            or record.fixture_date
            > window_end
        ):
            skipped += 1
            continue

        if (
            not record.player_a
            or not record.player_b
        ):
            skipped += 1
            continue

        existing = _find_existing(
            db,
            record,
        )

        if existing is None:
            row = Match(
                date=(
                    record.fixture_date
                ),
                tournament=(
                    record.tournament
                    or "MODUS"
                ),
                player_a=(
                    record.player_a
                ),
                player_b=(
                    record.player_b
                ),
                status=(
                    record.status
                    or "scheduled"
                ),
            )

            for field, value in {
                "stage": (
                    record.stage
                ),
                "match_format": (
                    record.match_format
                ),
                "winner": (
                    record.winner
                ),
                "score_a": (
                    record.score_a
                ),
                "score_b": (
                    record.score_b
                ),
                "provider_id": (
                    record.provider_id
                ),
            }.items():
                if (
                    value is not None
                    and hasattr(
                        row,
                        field,
                    )
                ):
                    setattr(
                        row,
                        field,
                        value,
                    )

            db.add(
                row
            )
            created += 1

            if (
                record.status
                == "completed"
            ):
                completed += 1

            continue

        previous_status = (
            getattr(
                existing,
                "status",
                None,
            )
        )

        changed = _apply_record(
            existing,
            record,
        )

        if changed:
            updated += 1

            if (
                previous_status
                != "completed"
                and record.status
                == "completed"
            ):
                completed += 1
        else:
            unchanged += 1

    if (
        created
        or updated
    ):
        db.commit()

    return FixtureSyncReport(
        scanned=len(
            records
        ),
        created=created,
        updated=updated,
        completed=completed,
        unchanged=unchanged,
        skipped=skipped,
        window_start=(
            window_start
        ),
        window_end=(
            window_end
        ),
        message=(
            "Fixture lifecycle sync completed."
        ),
    )


class CurrentSeriesLifecycleManager:
    def __init__(
        self,
        *,
        fetch_records: Callable[
            [date, date],
            Iterable[
                FixtureLifecycleRecord
            ],
        ],
        past_days: int = 7,
        future_days: int = 7,
    ) -> None:
        self.fetch_records = (
            fetch_records
        )
        self.past_days = max(
            1,
            int(
                past_days
            ),
        )
        self.future_days = max(
            1,
            int(
                future_days
            ),
        )

    def sync_once(
        self,
        db: Session,
        *,
        anchor_date: Optional[
            date
        ] = None,
    ) -> FixtureSyncReport:
        anchor = (
            anchor_date
            or date.today()
        )

        window_start = (
            anchor
            - timedelta(
                days=self.past_days
            )
        )

        window_end = (
            anchor
            + timedelta(
                days=self.future_days
            )
        )

        records = list(
            self.fetch_records(
                window_start,
                window_end,
            )
        )

        return (
            synchronise_fixture_records(
                db,
                records,
                window_start=(
                    window_start
                ),
                window_end=(
                    window_end
                ),
            )
        )
