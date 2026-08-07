import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.historical_series_sync_service import (
    HistoricalSeriesSyncService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakePreparation:
    action: str
    message: str = "Preparation result."

    @property
    def prepared(self):
        return self.action == "prepared"

    @property
    def complete(self):
        return self.action == "complete"


class FakePreparationService:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.error = None

    def run_cycle(self, *, root, catalog_html):
        self.calls.append((Path(root), catalog_html))
        if self.error:
            raise ValueError(self.error)
        return self.result


@dataclass
class FakeOrchestration:
    action: str
    message: str
    continue_running: bool
    error: str = None


class FakeOrchestratorService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run_cycle(self, db, *, root, watch_folder):
        self.calls.append((db, Path(root), watch_folder))
        return self.result


class FakeDb:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class HistoricalSeriesSyncServiceTests(unittest.TestCase):
    def build(self, preparation, orchestration=None):
        self.preparation_service = FakePreparationService(preparation)
        self.orchestrator_service = FakeOrchestratorService(
            orchestration
            or FakeOrchestration(
                action="complete",
                message="Complete.",
                continue_running=False,
            )
        )

        return HistoricalSeriesSyncService(
            preparation_service=self.preparation_service,
            orchestrator_service=self.orchestrator_service,
        )

    def test_prepares_missing_target_before_capture(self):
        service = self.build(
            FakePreparation(
                action="prepared",
                message="Prepared Group B.",
            )
        )
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.prepared)
        self.assertTrue(result.continue_running)
        self.assertEqual(result.message, "Prepared Group B.")
        self.assertEqual(self.orchestrator_service.calls, [])

    def test_capture_ready_runs_orchestrator(self):
        service = self.build(
            FakePreparation(
                action="capture_ready",
                message="Group A ready.",
            ),
            FakeOrchestration(
                action="captured",
                message="Captured match 16947.",
                continue_running=True,
            ),
        )
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
            catalog_html="<html></html>",
            watch_folder="~/Downloads",
        )

        self.assertTrue(result.captured)
        self.assertTrue(result.continue_running)
        self.assertEqual(
            self.orchestrator_service.calls,
            [(db, ROOT, "~/Downloads")],
        )

    def test_completed_capture_can_import(self):
        service = self.build(
            FakePreparation(action="complete"),
            FakeOrchestration(
                action="imported",
                message="Imported Group A.",
                continue_running=True,
            ),
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.imported)
        self.assertTrue(result.continue_running)

    def test_series_completes_only_when_both_layers_complete(self):
        service = self.build(
            FakePreparation(action="complete"),
            FakeOrchestration(
                action="complete",
                message="Library complete.",
                continue_running=False,
            ),
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.complete)
        self.assertFalse(result.continue_running)
        self.assertIn("fully captured", result.message)

    def test_orchestrator_complete_with_incomplete_preparation_continues(self):
        service = self.build(
            FakePreparation(
                action="capture_ready",
                message="Group B needs capture.",
            ),
            FakeOrchestration(
                action="complete",
                message="Current batch complete.",
                continue_running=False,
            ),
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "capture_ready")
        self.assertTrue(result.continue_running)

    def test_blocked_orchestration_is_propagated(self):
        service = self.build(
            FakePreparation(action="capture_ready"),
            FakeOrchestration(
                action="blocked",
                message="Validation blocked.",
                continue_running=False,
                error="Missing page.",
            ),
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertTrue(result.blocked)
        self.assertFalse(result.continue_running)
        self.assertEqual(result.error, "Missing page.")

    def test_preparation_exception_rolls_back(self):
        service = self.build(FakePreparation(action="prepared"))
        self.preparation_service.error = "Catalog failed."
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
            catalog_html="<html></html>",
        )

        self.assertEqual(result.action, "error")
        self.assertEqual(result.error, "Catalog failed.")
        self.assertTrue(db.rolled_back)


if __name__ == "__main__":
    unittest.main()
