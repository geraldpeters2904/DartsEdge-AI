import tempfile
import time
import unittest

from app.services.historical_workflow_worker import (
    HistoricalWorkflowWorker,
)


class FakeRunner:
    def __init__(self, status):
        self.status = status


class FakeWorkflowStatus:
    def __init__(self, status):
        self.runner = FakeRunner(status)


class FakeWorkflowService:
    def __init__(self):
        self.status = "running"
        self.calls = 0
        self.error = None

    def synchronise(self, root):
        self.calls += 1

        if self.error:
            raise ValueError(self.error)

        return FakeWorkflowStatus(self.status)

    def capture_iteration(self, root):
        return self.synchronise(root)


class HistoricalWorkflowWorkerTests(unittest.TestCase):
    def setUp(self):
        self.workflow = FakeWorkflowService()
        self.worker = HistoricalWorkflowWorker(
            workflow_service=self.workflow,
            interval_seconds=0.02,
        )

    def tearDown(self):
        for root in list(self.worker._statuses):
            self.worker.stop(root)

    def test_start_runs_background_synchronisation(self):
        with tempfile.TemporaryDirectory() as root:
            started = self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)
            self.worker.stop(root)

        self.assertTrue(started.running)
        self.assertGreaterEqual(status.iterations, 1)
        self.assertGreaterEqual(self.workflow.calls, 1)

    def test_start_is_idempotent_for_same_root(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.worker.start(root)
            second = self.worker.start(root)
            self.worker.stop(root)

        self.assertTrue(first.running)
        self.assertTrue(second.running)
        self.assertEqual(first.started_at, second.started_at)

    def test_worker_stops_when_workflow_completes(self):
        with tempfile.TemporaryDirectory() as root:
            self.workflow.status = "completed"

            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertGreaterEqual(status.iterations, 1)

    def test_worker_records_synchronisation_error(self):
        with tempfile.TemporaryDirectory() as root:
            self.workflow.error = "Synchronisation failed"

            self.worker.start(root)
            time.sleep(0.08)
            status = self.worker.status(root)

        self.assertFalse(status.running)
        self.assertEqual(
            status.last_error,
            "Synchronisation failed",
        )

    def test_stop_marks_worker_stopped(self):
        with tempfile.TemporaryDirectory() as root:
            self.worker.start(root)
            stopped = self.worker.stop(root)

        self.assertFalse(stopped.running)
        self.assertIn(
            "stopped",
            stopped.last_message.lower(),
        )


if __name__ == "__main__":
    unittest.main()
