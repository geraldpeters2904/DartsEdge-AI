import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.historical_automation_service import (
    HistoricalAutomationService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakePipelineResult:
    action: str
    message: str
    validation_issues: tuple = ()


class FakePipelineService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def run_cycle(self, db, *, root):
        self.calls.append((db, Path(root)))

        if self.error is not None:
            raise ValueError(self.error)

        return self.result


class HistoricalAutomationServiceTests(unittest.TestCase):
    def build(self, result=None, error=None):
        pipeline = FakePipelineService(
            result=result,
            error=error,
        )
        service = HistoricalAutomationService(
            pipeline_service=pipeline,
        )
        return service, pipeline

    def test_capture_action_continues(self):
        service, pipeline = self.build(
            FakePipelineResult(
                action="capture",
                message="Capture continues.",
            )
        )
        db = object()

        result = service.run_cycle(
            db,
            root=ROOT,
        )

        self.assertTrue(result.continue_running)
        self.assertFalse(result.completed)
        self.assertFalse(result.validation_failed)
        self.assertIsNone(result.error)
        self.assertEqual(result.action, "capture")
        self.assertEqual(
            pipeline.calls,
            [(db, ROOT)],
        )

    def test_import_action_continues(self):
        service, _ = self.build(
            FakePipelineResult(
                action="import",
                message="Import continues.",
            )
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertTrue(result.continue_running)
        self.assertEqual(result.action, "import")

    def test_complete_action_stops_successfully(self):
        service, _ = self.build(
            FakePipelineResult(
                action="complete",
                message="All work complete.",
            )
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertFalse(result.continue_running)
        self.assertTrue(result.completed)
        self.assertFalse(result.validation_failed)
        self.assertIsNone(result.error)

    def test_validation_action_stops_with_issue_detail(self):
        service, _ = self.build(
            FakePipelineResult(
                action="validate",
                message="Validation failed.",
                validation_issues=(
                    "Missing match_16947.html.",
                    "Player mismatch.",
                ),
            )
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertFalse(result.continue_running)
        self.assertFalse(result.completed)
        self.assertTrue(result.validation_failed)
        self.assertEqual(
            result.error,
            (
                "Missing match_16947.html.; "
                "Player mismatch."
            ),
        )

    def test_review_action_stops_without_error(self):
        service, _ = self.build(
            FakePipelineResult(
                action="review",
                message="Manual review required.",
            )
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertFalse(result.continue_running)
        self.assertFalse(result.completed)
        self.assertFalse(result.validation_failed)
        self.assertIsNone(result.error)

    def test_pipeline_exception_becomes_error_result(self):
        service, _ = self.build(
            error="Pipeline exploded.",
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertEqual(result.action, "error")
        self.assertFalse(result.continue_running)
        self.assertFalse(result.completed)
        self.assertFalse(result.validation_failed)
        self.assertEqual(
            result.error,
            "Pipeline exploded.",
        )

    def test_unknown_action_stops_with_error(self):
        service, _ = self.build(
            FakePipelineResult(
                action="mystery",
                message="Unexpected.",
            )
        )

        result = service.run_cycle(
            object(),
            root=ROOT,
        )

        self.assertFalse(result.continue_running)
        self.assertIn(
            "Unknown historical automation action",
            result.error,
        )


if __name__ == "__main__":
    unittest.main()
