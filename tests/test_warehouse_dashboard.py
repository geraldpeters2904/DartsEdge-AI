import tempfile
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.historical_import import HistoricalImportBatch
from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.warehouse_dashboard_service import (
    WarehouseDashboardService,
)
from tests.helpers.database import create_test_session


@dataclass
class FakePlan:
    imported_folders: int = 1
    queued_folders: int = 0
    incomplete_folders: int = 0
    partially_imported_folders: int = 0
    error_folders: int = 0
    expected_matches: int = 45
    imported_matches: int = 45
    remaining_matches: int = 0
    coverage_percent: float = 100.0
    blocking_issues: tuple = ()

    @property
    def blocked(self):
        return bool(self.blocking_issues)


class FakePopulationService:
    def __init__(self, plan=None):
        self.plan = plan or FakePlan()

    def build_plan(self, db, *, root):
        return self.plan


@dataclass
class FakeCaptureSummary:
    sessions: int = 1
    complete_sessions: int = 1
    in_progress_sessions: int = 0
    expected_matches: int = 45
    captured_matches: int = 45
    missing_matches: int = 0


@dataclass
class FakeCaptureLibrary:
    summary: FakeCaptureSummary


class FakeCaptureLibraryService:
    def __init__(self, summary=None):
        self.summary = summary or FakeCaptureSummary()

    def scan(self, root):
        return FakeCaptureLibrary(self.summary)


class WarehouseDashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = WarehouseDashboardService(
            population_service=FakePopulationService(),
            capture_library_service=(
                FakeCaptureLibraryService()
            ),
        )

    def tearDown(self):
        self.db.close()

    def seed(self):
        player_a = Player(name="Player A")
        player_b = Player(name="Player B")
        self.db.add_all([player_a, player_b])
        self.db.flush()

        completed = Match(
            status="completed",
            player_a="Player A",
            player_b="Player B",
            winner="Player A",
            score="4-2",
        )
        scheduled = Match(
            status="scheduled",
            player_a="Player A",
            player_b="Player B",
        )
        self.db.add_all([completed, scheduled])
        self.db.flush()

        self.db.add_all([
            PlayerMatchPerformance(
                match_id=completed.id,
                player_id=player_a.id,
                opponent_id=player_b.id,
                source_provider="modus-official",
            ),
            PlayerMatchPerformance(
                match_id=completed.id,
                player_id=player_b.id,
                opponent_id=player_a.id,
                source_provider="modus-official",
            ),
        ])

        self.db.add(
            HistoricalImportBatch(
                batch_uuid="batch-1",
                filename="fixtures.csv",
                provider="modus-official",
                competition_code="MODUS",
                status="imported",
                received_rows=45,
                created_matches=45,
                duplicate_matches=0,
                rejected_rows=0,
                created_players=6,
                created_at=datetime(2026, 8, 3, 17, 0),
            )
        )
        self.db.commit()

    def test_builds_live_warehouse_snapshot(self):
        self.seed()

        with tempfile.TemporaryDirectory() as root:
            snapshot = self.service.build(
                self.db,
                capture_root=root,
            )

        self.assertEqual(snapshot.total_matches, 2)
        self.assertEqual(snapshot.completed_matches, 1)
        self.assertEqual(snapshot.scheduled_matches, 1)
        self.assertEqual(snapshot.players, 2)
        self.assertEqual(snapshot.statistics, 2)
        self.assertEqual(snapshot.import_batches, 1)
        self.assertEqual(snapshot.coverage_percent, 100.0)
        self.assertEqual(snapshot.health_score, 100.0)
        self.assertEqual(snapshot.health_label, "Excellent")

    def test_api_payload_contains_stable_sections(self):
        payload = self.service.build(
            self.db,
            capture_root="/tmp/history",
        ).to_dict()

        self.assertEqual(
            set(payload),
            {
                "matches",
                "players",
                "statistics",
                "import_batches",
                "population",
                "capture",
                "health",
                "recent_imports",
                "database",
                "generated_at",
            },
        )

    def test_blocking_and_missing_data_reduce_health(self):
        service = WarehouseDashboardService(
            population_service=FakePopulationService(
                FakePlan(
                    expected_matches=45,
                    imported_matches=0,
                    remaining_matches=45,
                    coverage_percent=0.0,
                    blocking_issues=("Missing folder.",),
                )
            ),
            capture_library_service=(
                FakeCaptureLibraryService(
                    FakeCaptureSummary(
                        sessions=1,
                        complete_sessions=0,
                        in_progress_sessions=1,
                        expected_matches=45,
                        captured_matches=40,
                        missing_matches=5,
                    )
                )
            ),
        )

        with tempfile.TemporaryDirectory() as root:
            snapshot = service.build(
                self.db,
                capture_root=root,
            )

        self.assertLess(snapshot.health_score, 100.0)
        self.assertNotEqual(
            snapshot.health_label,
            "Excellent",
        )


class WarehouseDashboardRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_dashboard_page_returns_200(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/warehouse-dashboard",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'data-testid="warehouse-metrics"',
            response.text,
        )
        self.assertIn(
            'data-testid="warehouse-coverage"',
            response.text,
        )
        self.assertIn(
            'data-testid="warehouse-health"',
            response.text,
        )
        self.assertIn("Auto-refreshing", response.text)

    def test_dashboard_api_returns_json(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/api/warehouse/dashboard",
                params={"capture_root": root},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("matches", payload)
        self.assertIn("population", payload)
        self.assertIn("health", payload)
        self.assertIn("capture", payload)


if __name__ == "__main__":
    unittest.main()
