from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.historical_import import HistoricalImportBatch
from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.capture_library_service import (
    CaptureLibraryService,
    DEFAULT_CAPTURE_ROOT,
)
from app.services.warehouse_population_service import (
    WarehousePopulationPlan,
    WarehousePopulationService,
)


@dataclass(frozen=True)
class WarehouseRecentImport:
    batch_id: int
    batch_uuid: str
    created_at: Optional[str]
    status: str
    provider: str
    competition: str
    created_matches: int
    duplicate_matches: int
    rejected_rows: int


@dataclass(frozen=True)
class WarehouseMetric:
    key: str
    label: str
    value: object
    detail: str = ""


@dataclass(frozen=True)
class WarehouseHealthItem:
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class WarehouseDashboardSnapshot:
    total_matches: int
    completed_matches: int
    scheduled_matches: int
    players: int
    statistics: int
    import_batches: int
    imported_groups: int
    queued_groups: int
    incomplete_groups: int
    partially_imported_groups: int
    error_groups: int
    expected_historical_matches: int
    imported_historical_matches: int
    remaining_historical_matches: int
    coverage_percent: float
    capture_sessions: int
    capture_complete_sessions: int
    capture_in_progress_sessions: int
    capture_expected_pages: int
    capture_captured_pages: int
    capture_missing_pages: int
    health_score: float
    health_label: str
    blocking_issues: List[str]
    recent_imports: List[WarehouseRecentImport]
    database_path: Optional[str]
    database_size_bytes: Optional[int]
    generated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def metrics(self) -> List[WarehouseMetric]:
        return [
            WarehouseMetric(
                "matches",
                "Historical Matches",
                self.total_matches,
                (
                    f"{self.completed_matches} completed · "
                    f"{self.scheduled_matches} scheduled"
                ),
            ),
            WarehouseMetric(
                "players",
                "Players",
                self.players,
                "Unique warehouse players",
            ),
            WarehouseMetric(
                "statistics",
                "Statistics",
                self.statistics,
                "Player-match performance rows",
            ),
            WarehouseMetric(
                "coverage",
                "Coverage",
                f"{self.coverage_percent:.1f}%",
                (
                    f"{self.imported_historical_matches} of "
                    f"{self.expected_historical_matches} expected matches"
                ),
            ),
            WarehouseMetric(
                "groups",
                "Imported Groups",
                self.imported_groups,
                f"{self.queued_groups} ready to import",
            ),
            WarehouseMetric(
                "capture",
                "Captured Pages",
                self.capture_captured_pages,
                f"{self.capture_missing_pages} page(s) missing",
            ),
            WarehouseMetric(
                "batches",
                "Import Batches",
                self.import_batches,
                "Recorded warehouse commits",
            ),
            WarehouseMetric(
                "health",
                "Health",
                f"{self.health_score:.1f}%",
                self.health_label,
            ),
        ]

    @property
    def capture_summary(self) -> Dict[str, int]:
        return {
            "sessions": self.capture_sessions,
            "complete_sessions": self.capture_complete_sessions,
            "in_progress_sessions": self.capture_in_progress_sessions,
            "expected_matches": self.capture_expected_pages,
            "captured_matches": self.capture_captured_pages,
            "missing_matches": self.capture_missing_pages,
        }

    @property
    def table_counts(self) -> Dict[str, int]:
        return {
            "players": self.players,
            "fixtures": self.total_matches,
            "matches": self.total_matches,
            "statistics": self.statistics,
            "imports": self.import_batches,
        }

    @property
    def health(self) -> List[WarehouseHealthItem]:
        return [
            WarehouseHealthItem(
                "Warehouse health",
                (
                    "healthy"
                    if self.health_score >= 90
                    else "warning"
                ),
                (
                    f"{self.health_label} "
                    f"({self.health_score:.1f}%)."
                ),
            ),
            WarehouseHealthItem(
                "Historical coverage",
                (
                    "healthy"
                    if self.coverage_percent >= 95
                    else "warning"
                ),
                (
                    f"{self.coverage_percent:.1f}% populated; "
                    f"{self.remaining_historical_matches} match(es) remain."
                ),
            ),
            WarehouseHealthItem(
                "Capture library",
                (
                    "healthy"
                    if self.capture_missing_pages == 0
                    else "warning"
                ),
                (
                    f"{self.capture_captured_pages} of "
                    f"{self.capture_expected_pages} pages captured."
                ),
            ),
            WarehouseHealthItem(
                "Validation blockers",
                (
                    "healthy"
                    if not self.blocking_issues
                    else "warning"
                ),
                (
                    "No blocking issues."
                    if not self.blocking_issues
                    else (
                        f"{len(self.blocking_issues)} issue(s) "
                        "require attention."
                    )
                ),
            ),
        ]

    def to_dict(self) -> Dict[str, object]:
        return {
            "matches": {
                "total": self.total_matches,
                "completed": self.completed_matches,
                "scheduled": self.scheduled_matches,
            },
            "players": self.players,
            "statistics": self.statistics,
            "import_batches": self.import_batches,
            "population": {
                "imported_groups": self.imported_groups,
                "queued_groups": self.queued_groups,
                "incomplete_groups": self.incomplete_groups,
                "partially_imported_groups": (
                    self.partially_imported_groups
                ),
                "error_groups": self.error_groups,
                "expected_matches": self.expected_historical_matches,
                "imported_matches": self.imported_historical_matches,
                "remaining_matches": self.remaining_historical_matches,
                "coverage_percent": self.coverage_percent,
                "blocking_issues": list(self.blocking_issues),
            },
            "capture": {
                "sessions": self.capture_sessions,
                "complete_sessions": self.capture_complete_sessions,
                "in_progress_sessions": (
                    self.capture_in_progress_sessions
                ),
                "expected_pages": self.capture_expected_pages,
                "captured_pages": self.capture_captured_pages,
                "missing_pages": self.capture_missing_pages,
            },
            "health": {
                "score": self.health_score,
                "label": self.health_label,
            },
            "recent_imports": [
                {
                    "batch_id": item.batch_id,
                    "batch_uuid": item.batch_uuid,
                    "created_at": item.created_at,
                    "status": item.status,
                    "provider": item.provider,
                    "competition": item.competition,
                    "created_matches": item.created_matches,
                    "duplicate_matches": item.duplicate_matches,
                    "rejected_rows": item.rejected_rows,
                }
                for item in self.recent_imports
            ],
            "database": {
                "path": self.database_path,
                "size_bytes": self.database_size_bytes,
            },
            "generated_at": self.generated_at.isoformat(),
        }


# Backward-compatible public name used by Operations services.
WarehouseDashboard = WarehouseDashboardSnapshot


class WarehouseDashboardService:
    """Build one read-only operational warehouse snapshot."""

    def __init__(
        self,
        *,
        population_service: Optional[
            WarehousePopulationService
        ] = None,
        capture_library_service: Optional[
            CaptureLibraryService
        ] = None,
    ) -> None:
        self.population_service = (
            population_service or WarehousePopulationService()
        )
        self.capture_library_service = (
            capture_library_service or CaptureLibraryService()
        )

    def build(
        self,
        db: Session,
        *,
        capture_root: str | Path = DEFAULT_CAPTURE_ROOT,
    ) -> WarehouseDashboardSnapshot:
        root = Path(capture_root).expanduser().resolve()

        total_matches = int(
            db.query(func.count(Match.id)).scalar() or 0
        )
        completed_matches = int(
            db.query(func.count(Match.id))
            .filter(func.lower(Match.status) == "completed")
            .scalar()
            or 0
        )
        scheduled_matches = int(
            db.query(func.count(Match.id))
            .filter(func.lower(Match.status) == "scheduled")
            .scalar()
            or 0
        )
        players = int(
            db.query(func.count(Player.id)).scalar() or 0
        )
        statistics = int(
            db.query(func.count(PlayerMatchPerformance.id))
            .scalar()
            or 0
        )
        import_batches = int(
            db.query(func.count(HistoricalImportBatch.id))
            .scalar()
            or 0
        )

        plan = self.population_service.build_plan(
            db,
            root=root,
        )
        capture_library = self.capture_library_service.scan(root)

        recent_imports = self._recent_imports(db)
        health_score, health_label = self._health(
            total_matches=total_matches,
            completed_matches=completed_matches,
            statistics=statistics,
            plan=plan,
            missing_pages=(
                capture_library.summary.missing_matches
            ),
            rejected_rows=sum(
                item.rejected_rows
                for item in recent_imports
            ),
        )
        database_path, database_size = self._database_file(db)

        return WarehouseDashboardSnapshot(
            total_matches=total_matches,
            completed_matches=completed_matches,
            scheduled_matches=scheduled_matches,
            players=players,
            statistics=statistics,
            import_batches=import_batches,
            imported_groups=plan.imported_folders,
            queued_groups=plan.queued_folders,
            incomplete_groups=plan.incomplete_folders,
            partially_imported_groups=(
                plan.partially_imported_folders
            ),
            error_groups=plan.error_folders,
            expected_historical_matches=plan.expected_matches,
            imported_historical_matches=plan.imported_matches,
            remaining_historical_matches=plan.remaining_matches,
            coverage_percent=plan.coverage_percent,
            capture_sessions=(
                capture_library.summary.sessions
            ),
            capture_complete_sessions=(
                capture_library.summary.complete_sessions
            ),
            capture_in_progress_sessions=(
                capture_library.summary.in_progress_sessions
            ),
            capture_expected_pages=(
                capture_library.summary.expected_matches
            ),
            capture_captured_pages=(
                capture_library.summary.captured_matches
            ),
            capture_missing_pages=(
                capture_library.summary.missing_matches
            ),
            health_score=health_score,
            health_label=health_label,
            blocking_issues=list(plan.blocking_issues),
            recent_imports=recent_imports,
            database_path=database_path,
            database_size_bytes=database_size,
        )

    @staticmethod
    def _recent_imports(
        db: Session,
        *,
        limit: int = 10,
    ) -> List[WarehouseRecentImport]:
        records = (
            db.query(HistoricalImportBatch)
            .order_by(
                HistoricalImportBatch.created_at.desc(),
                HistoricalImportBatch.id.desc(),
            )
            .limit(max(1, min(int(limit), 50)))
            .all()
        )

        return [
            WarehouseRecentImport(
                batch_id=record.id,
                batch_uuid=record.batch_uuid,
                created_at=(
                    record.created_at.isoformat()
                    if record.created_at
                    else None
                ),
                status=record.status,
                provider=record.provider,
                competition=record.competition_code,
                created_matches=record.created_matches,
                duplicate_matches=record.duplicate_matches,
                rejected_rows=record.rejected_rows,
            )
            for record in records
        ]

    @staticmethod
    def _health(
        *,
        total_matches: int,
        completed_matches: int,
        statistics: int,
        plan: WarehousePopulationPlan,
        missing_pages: int,
        rejected_rows: int,
    ) -> tuple[float, str]:
        deductions = 0.0

        if plan.blocked:
            deductions += min(
                30.0,
                5.0 * len(plan.blocking_issues),
            )

        if missing_pages:
            deductions += min(20.0, missing_pages * 0.5)

        if rejected_rows:
            deductions += min(20.0, rejected_rows * 2.0)

        expected_statistics = completed_matches * 2

        if expected_statistics:
            missing_statistics = max(
                expected_statistics - statistics,
                0,
            )
            deductions += min(
                25.0,
                missing_statistics
                / expected_statistics
                * 25.0,
            )
        elif total_matches and statistics == 0:
            deductions += 15.0

        score = round(max(0.0, 100.0 - deductions), 1)

        if score >= 98:
            label = "Excellent"
        elif score >= 90:
            label = "Healthy"
        elif score >= 75:
            label = "Needs attention"
        else:
            label = "Action required"

        return score, label

    @staticmethod
    def _database_file(
        db: Session,
    ) -> tuple[Optional[str], Optional[int]]:
        bind = db.get_bind()
        url = bind.url

        if url.get_backend_name() != "sqlite":
            return None, None

        database = url.database

        if not database or database == ":memory:":
            return database, None

        path = Path(database).expanduser().resolve()

        return (
            str(path),
            path.stat().st_size if path.exists() else 0,
        )
