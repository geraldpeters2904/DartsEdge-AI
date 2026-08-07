from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.historical_archive_plan_service import HistoricalArchivePlanService
from app.services.historical_import_manager_service import HistoricalImportManagerService
from app.services.historical_runner_service import HistoricalRunnerService


@dataclass(frozen=True)
class WarehouseHealthMetrics:
    root: Path
    discovered_series: int
    complete_series: int
    remaining_series: int
    discovered_groups: int
    ready_groups: int
    incomplete_groups: int
    imported_groups: int
    partially_imported_groups: int
    error_groups: int
    expected_matches: int
    validated_matches: int
    missing_matches: int
    imported_fixture_mappings: int
    database_players: int
    database_matches: int
    database_performances: int
    runner_status: str
    runner_processed_matches: int
    runner_remaining_matches: int
    runner_total_matches: int
    runner_current_series: Optional[str]
    runner_current_week: Optional[str]
    runner_current_group: Optional[str]
    runner_current_match_id: Optional[int]
    runner_last_message: str
    runner_last_error: Optional[str]

    @property
    def series_completion_percentage(self) -> float:
        if self.discovered_series == 0:
            return 0.0
        return round(self.complete_series / self.discovered_series * 100.0, 3)

    @property
    def validation_percentage(self) -> float:
        if self.expected_matches == 0:
            return 0.0
        return round(self.validated_matches / self.expected_matches * 100.0, 3)

    @property
    def runner_completion_percentage(self) -> float:
        if self.runner_total_matches == 0:
            return 0.0
        return round(
            self.runner_processed_matches / self.runner_total_matches * 100.0,
            3,
        )

    @property
    def healthy(self) -> bool:
        return self.error_groups == 0 and not self.runner_last_error


class WarehouseMetricsService:
    def __init__(
        self,
        *,
        archive_plan_service=None,
        import_manager_service=None,
        runner_service=None,
    ) -> None:
        self.archive_plan_service = archive_plan_service or HistoricalArchivePlanService()
        self.import_manager_service = import_manager_service or HistoricalImportManagerService()
        self.runner_service = runner_service or HistoricalRunnerService()

    def collect(self, db: Session, *, root, catalog_html: str) -> WarehouseHealthMetrics:
        root_path = Path(root).expanduser().resolve()
        plan = self.archive_plan_service.build_plan(
            root=root_path,
            catalog_html=catalog_html,
        )
        library = self.import_manager_service.scan(db, root_path)
        runner = self.runner_service.load(root_path)

        expected_matches = sum(item.expected_count for item in library.folders)
        validated_matches = sum(item.validated_count for item in library.folders)
        missing_matches = sum(item.missing_count for item in library.folders)

        return WarehouseHealthMetrics(
            root=root_path,
            discovered_series=plan.discovered_series,
            complete_series=plan.complete_series,
            remaining_series=plan.remaining_series,
            discovered_groups=library.discovered_count,
            ready_groups=library.ready_count,
            incomplete_groups=library.incomplete_count,
            imported_groups=library.imported_count,
            partially_imported_groups=library.partially_imported_count,
            error_groups=library.error_count,
            expected_matches=expected_matches,
            validated_matches=validated_matches,
            missing_matches=missing_matches,
            imported_fixture_mappings=(
                db.query(ProviderEntityMapping)
                .filter(
                    ProviderEntityMapping.provider == "modus-official",
                    ProviderEntityMapping.entity_type == "fixture",
                )
                .count()
            ),
            database_players=db.query(Player).count(),
            database_matches=db.query(Match).count(),
            database_performances=db.query(PlayerMatchPerformance).count(),
            runner_status=runner.status,
            runner_processed_matches=runner.processed_matches,
            runner_remaining_matches=runner.remaining_matches,
            runner_total_matches=runner.total_matches,
            runner_current_series=runner.current_series_label,
            runner_current_week=runner.current_week_label,
            runner_current_group=runner.current_group,
            runner_current_match_id=runner.current_match_id,
            runner_last_message=runner.last_message,
            runner_last_error=runner.last_error,
        )
