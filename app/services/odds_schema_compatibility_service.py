from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import engine


NEW_COLUMNS = {
    "fixture_id": "INTEGER",
    "bookmaker_code": "VARCHAR",
    "implied_probability": "FLOAT",
    "source_reference": "VARCHAR",
}


def _normalise_bookmaker(value: str | None) -> str | None:
    if not value:
        return None

    return "".join(
        ch
        for ch in str(value).strip().casefold()
        if ch.isalnum()
    )


def ensure_odds_snapshot_compatibility() -> dict:
    """
    Upgrade an older odds_snapshots SQLite table in place.

    Existing rows and legacy columns are preserved. New Sprint 2 columns
    are added only when missing, then backfilled where possible.
    """
    inspector = inspect(engine)

    if "odds_snapshots" not in inspector.get_table_names():
        return {
            "table_exists": False,
            "columns_added": [],
            "rows_backfilled": 0,
        }

    existing = {
        column["name"]
        for column in inspector.get_columns(
            "odds_snapshots"
        )
    }

    added = []

    with engine.begin() as connection:
        for name, sql_type in NEW_COLUMNS.items():
            if name in existing:
                continue

            connection.execute(
                text(
                    f"ALTER TABLE odds_snapshots "
                    f"ADD COLUMN {name} {sql_type}"
                )
            )
            added.append(name)

        # Backfill bookmaker_code from the legacy bookmaker field.
        if "bookmaker" in existing or "bookmaker" in {
            column["name"]
            for column in inspect(engine).get_columns("odds_snapshots")
        }:
            rows = connection.execute(
                text(
                    "SELECT id, bookmaker "
                    "FROM odds_snapshots "
                    "WHERE bookmaker_code IS NULL"
                )
            ).fetchall()

            for row in rows:
                code = _normalise_bookmaker(
                    row.bookmaker
                )

                if code:
                    connection.execute(
                        text(
                            "UPDATE odds_snapshots "
                            "SET bookmaker_code = :code "
                            "WHERE id = :row_id"
                        ),
                        {
                            "code": code,
                            "row_id": row.id,
                        },
                    )

        # Backfill implied probability from decimal odds.
        connection.execute(
            text(
                "UPDATE odds_snapshots "
                "SET implied_probability = "
                "CASE "
                "WHEN decimal_odds > 1.0 "
                "THEN 100.0 / decimal_odds "
                "ELSE NULL "
                "END "
                "WHERE implied_probability IS NULL"
            )
        )

        # Preserve the best available legacy source reference.
        columns_now = {
            column["name"]
            for column in inspect(engine).get_columns(
                "odds_snapshots"
            )
        }

        if "provider_id" in columns_now:
            connection.execute(
                text(
                    "UPDATE odds_snapshots "
                    "SET source_reference = provider_id "
                    "WHERE source_reference IS NULL "
                    "AND provider_id IS NOT NULL"
                )
            )

        if "external_id" in columns_now:
            connection.execute(
                text(
                    "UPDATE odds_snapshots "
                    "SET source_reference = external_id "
                    "WHERE source_reference IS NULL "
                    "AND external_id IS NOT NULL"
                )
            )

        # Resolve legacy rows to Match.id by date + player pairing.
        if {
            "fixture_date",
            "player_a",
            "player_b",
        }.issubset(columns_now):
            connection.execute(
                text(
                    """
                    UPDATE odds_snapshots
                    SET fixture_id = (
                        SELECT matches.id
                        FROM matches
                        WHERE matches.date = odds_snapshots.fixture_date
                          AND (
                            (
                              lower(trim(matches.player_a))
                              = lower(trim(odds_snapshots.player_a))
                              AND
                              lower(trim(matches.player_b))
                              = lower(trim(odds_snapshots.player_b))
                            )
                            OR
                            (
                              lower(trim(matches.player_a))
                              = lower(trim(odds_snapshots.player_b))
                              AND
                              lower(trim(matches.player_b))
                              = lower(trim(odds_snapshots.player_a))
                            )
                          )
                        ORDER BY matches.id ASC
                        LIMIT 1
                    )
                    WHERE fixture_id IS NULL
                    """
                )
            )

        backfilled = connection.execute(
            text(
                "SELECT COUNT(*) "
                "FROM odds_snapshots "
                "WHERE fixture_id IS NOT NULL "
                "AND bookmaker_code IS NOT NULL "
                "AND implied_probability IS NOT NULL"
            )
        ).scalar() or 0

    return {
        "table_exists": True,
        "columns_added": added,
        "rows_backfilled": int(
            backfilled
        ),
    }
