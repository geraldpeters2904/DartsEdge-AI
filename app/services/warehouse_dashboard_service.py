from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.services.capture_library_service import (
    CaptureLibraryService,
    DEFAULT_CAPTURE_ROOT,
)


_TABLE_CANDIDATES = {
    "players": ("players", "player"),
    "fixtures": ("fixtures", "canonical_fixtures", "match_fixtures", "matches"),
    "matches": ("matches", "canonical_matches", "results"),
    "statistics": (
        "match_statistics",
        "statistics",
        "player_match_statistics",
        "canonical_statistics",
        "match_player_stats",
    ),
    "imports": (
        "collector_imports",
        "import_sessions",
        "historical_imports",
        "collector_previews",
        "historical_import_previews",
        "historical_import_batches",
    ),
}


@dataclass(frozen=True)
class WarehouseMetric:
    key: str
    label: str
    value: int
    detail: str = ""


@dataclass(frozen=True)
class WarehouseHealthItem:
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class WarehouseRecentImport:
    identifier: str
    created_at: Optional[str]
    status: str
    provider: str
    competition: str


@dataclass(frozen=True)
class WarehouseDashboard:
    metrics: List[WarehouseMetric]
    health: List[WarehouseHealthItem]
    recent_imports: List[WarehouseRecentImport]
    capture_summary: Dict[str, int]
    table_counts: Dict[str, int]
    database_path: Optional[str]
    database_size_bytes: Optional[int]
    generated_at: datetime = field(default_factory=datetime.utcnow)


class WarehouseDashboardService:
    """Read-only operational summary of warehouse and capture progress."""

    def __init__(self):
        self.capture_library_service = CaptureLibraryService()

    def build(
        self,
        db: Session,
        *,
        capture_root: str | Path = DEFAULT_CAPTURE_ROOT,
    ) -> WarehouseDashboard:
        bind = db.get_bind()
        inspector = inspect(bind)
        table_names = set(inspector.get_table_names())

        resolved = {
            key: self._first_existing(table_names, candidates)
            for key, candidates in _TABLE_CANDIDATES.items()
        }

        table_counts = {
            key: self._count_table(db, table)
            if table is not None else 0
            for key, table in resolved.items()
        }

        fixture_table = resolved["fixtures"]
        scheduled = self._count_status(
            db,
            fixture_table,
            ("scheduled", "upcoming", "not_started"),
        )
        completed = self._count_status(
            db,
            fixture_table,
            ("completed", "finished", "closed"),
        )

        capture_library = self.capture_library_service.scan(capture_root)
        capture_summary = {
            "sessions": capture_library.summary.sessions,
            "complete_sessions": capture_library.summary.complete_sessions,
            "in_progress_sessions": capture_library.summary.in_progress_sessions,
            "expected_matches": capture_library.summary.expected_matches,
            "captured_matches": capture_library.summary.captured_matches,
            "missing_matches": capture_library.summary.missing_matches,
        }

        metrics = [
            WarehouseMetric("players", "Players", table_counts["players"], "Tracked warehouse players"),
            WarehouseMetric("fixtures", "Fixtures", table_counts["fixtures"], "All canonical fixtures"),
            WarehouseMetric("matches", "Matches", table_counts["matches"], "Imported match results"),
            WarehouseMetric("statistics", "Statistics", table_counts["statistics"], "Player-match statistic rows"),
            WarehouseMetric("scheduled", "Scheduled", scheduled, "Upcoming fixtures"),
            WarehouseMetric("completed", "Completed", completed, "Completed fixtures"),
            WarehouseMetric(
                "captured",
                "Captured Pages",
                capture_library.summary.captured_matches,
                f"of {capture_library.summary.expected_matches} expected capture pages",
            ),
            WarehouseMetric(
                "missing",
                "Missing Pages",
                capture_library.summary.missing_matches,
                "Outstanding browser-assisted captures",
            ),
        ]

        health = self._build_health(
            table_names=table_names,
            resolved=resolved,
            capture_summary=capture_summary,
        )
        recent_imports = self._recent_imports(db, resolved["imports"], inspector)
        database_path, database_size = self._database_file(bind)

        return WarehouseDashboard(
            metrics=metrics,
            health=health,
            recent_imports=recent_imports,
            capture_summary=capture_summary,
            table_counts=table_counts,
            database_path=database_path,
            database_size_bytes=database_size,
        )

    @staticmethod
    def _first_existing(table_names: set[str], candidates: tuple[str, ...]) -> Optional[str]:
        return next((name for name in candidates if name in table_names), None)

    @staticmethod
    def _count_table(db: Session, table: str) -> int:
        return int(db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one())

    @staticmethod
    def _count_status(
        db: Session,
        table: Optional[str],
        statuses: tuple[str, ...],
    ) -> int:
        if table is None:
            return 0

        inspector = inspect(db.get_bind())
        columns = {column["name"] for column in inspector.get_columns(table)}
        status_column = next(
            (name for name in ("status", "match_status", "fixture_status") if name in columns),
            None,
        )
        if status_column is None:
            return 0

        placeholders = ", ".join(f":status_{index}" for index in range(len(statuses)))
        params = {f"status_{index}": status for index, status in enumerate(statuses)}
        result = db.execute(
            text(
                f'SELECT COUNT(*) FROM "{table}" '
                f'WHERE LOWER("{status_column}") IN ({placeholders})'
            ),
            params,
        ).scalar_one()
        return int(result)

    @staticmethod
    def _build_health(
        *,
        table_names: set[str],
        resolved: Dict[str, Optional[str]],
        capture_summary: Dict[str, int],
    ) -> List[WarehouseHealthItem]:
        items = [
            WarehouseHealthItem(
                "Fixture warehouse",
                "healthy" if resolved["fixtures"] else "warning",
                (
                    f'Using table "{resolved["fixtures"]}".'
                    if resolved["fixtures"]
                    else "No recognised fixture table exists yet."
                ),
            ),
            WarehouseHealthItem(
                "Player warehouse",
                "healthy" if resolved["players"] else "warning",
                (
                    f'Using table "{resolved["players"]}".'
                    if resolved["players"]
                    else "No recognised player table exists yet."
                ),
            ),
        ]

        missing = capture_summary["missing_matches"]
        items.append(
            WarehouseHealthItem(
                "Capture completeness",
                "healthy" if missing == 0 else "warning",
                (
                    "All tracked capture pages are present."
                    if missing == 0
                    else f"{missing} capture page(s) are still missing."
                ),
            )
        )
        items.append(
            WarehouseHealthItem(
                "Database connection",
                "healthy",
                f"{len(table_names)} table(s) detected.",
            )
        )
        return items

    @staticmethod
    def _recent_imports(
        db: Session,
        table: Optional[str],
        inspector,
    ) -> List[WarehouseRecentImport]:
        if table is None:
            return []

        columns = {column["name"] for column in inspector.get_columns(table)}
        id_column = next((name for name in ("preview_uuid", "import_uuid", "id", "uuid") if name in columns), None)
        created_column = next((name for name in ("created_at", "started_at", "imported_at", "updated_at") if name in columns), None)
        status_column = next((name for name in ("status", "state", "result") if name in columns), None)
        provider_column = next((name for name in ("provider", "source_provider") if name in columns), None)
        competition_column = next((name for name in ("competition", "competition_code") if name in columns), None)

        selected = [c for c in (id_column, created_column, status_column, provider_column, competition_column) if c]
        if not selected:
            return []

        sql_columns = ", ".join(f'"{column}"' for column in selected)
        order_sql = f' ORDER BY "{created_column}" DESC' if created_column else ""
        rows = db.execute(
            text(f'SELECT {sql_columns} FROM "{table}"{order_sql} LIMIT 8')
        ).mappings().all()

        return [
            WarehouseRecentImport(
                identifier=str(row.get(id_column, "—") if id_column else "—"),
                created_at=str(row.get(created_column)) if created_column and row.get(created_column) is not None else None,
                status=str(row.get(status_column, "unknown") if status_column else "unknown"),
                provider=str(row.get(provider_column, "—") if provider_column else "—"),
                competition=str(row.get(competition_column, "—") if competition_column else "—"),
            )
            for row in rows
        ]

    @staticmethod
    def _database_file(bind) -> tuple[Optional[str], Optional[int]]:
        url = bind.url
        if url.get_backend_name() != "sqlite":
            return None, None
        database = url.database
        if not database or database == ":memory:":
            return database, None
        path = Path(database).expanduser().resolve()
        return str(path), path.stat().st_size if path.exists() else None
