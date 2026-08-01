import json
import tempfile
import unittest
from pathlib import Path

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchService,
)
from app.services.historical_runner_service import (
    RUNNER_FILENAME,
    HistoricalRunnerService,
)


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalRunnerServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def setUp(self):
        self.batch_service = HistoricalCaptureBatchService()
        self.service = HistoricalRunnerService()

    def create_batch(self, root):
        return self.batch_service.create(
            root=root,
            results_pages=[
                (
                    "series14-week01-group-a.html",
                    self.results_html,
                )
            ],
        )

    def test_load_without_state_returns_stopped(self):
        with tempfile.TemporaryDirectory() as root:
            state = self.service.load(root)

        self.assertEqual(state.status, "stopped")
        self.assertTrue(state.stopped)
        self.assertTrue(state.can_start)
        self.assertFalse(state.running)

    def test_start_persists_current_batch_position(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.create_batch(root)
            state = self.service.start(root)

            state_path = Path(root, RUNNER_FILENAME)

            self.assertTrue(state_path.is_file())

            payload = json.loads(
                state_path.read_text(encoding="utf-8")
            )

        self.assertTrue(state.running)
        self.assertEqual(state.current_position, 1)
        self.assertEqual(state.current_series_id, 14)
        self.assertEqual(state.current_week_id, 165)
        self.assertEqual(state.current_week_label, "Week 1")
        self.assertEqual(state.current_group, "Group A")
        self.assertEqual(
            state.current_match_id,
            batch.next_item.next_match_id,
        )
        self.assertEqual(payload["status"], "running")

    def test_pause_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)
            self.service.start(root)

            paused = self.service.pause(root)
            resumed = self.service.resume(root)

        self.assertTrue(paused.paused)
        self.assertTrue(paused.can_resume)
        self.assertIsNotNone(paused.paused_at)

        self.assertTrue(resumed.running)
        self.assertFalse(resumed.paused)
        self.assertIsNone(resumed.paused_at)

    def test_stop_preserves_current_position(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_batch(root)
            started = self.service.start(root)
            stopped = self.service.stop(root)

        self.assertTrue(stopped.stopped)
        self.assertEqual(
            stopped.current_position,
            started.current_position,
        )
        self.assertEqual(
            stopped.current_match_id,
            started.current_match_id,
        )
        self.assertIsNotNone(stopped.stopped_at)

    def test_state_advances_when_capture_progress_changes(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.create_batch(root)
            started = self.service.start(root)

            session_path = (
                batch.next_item.destination_folder
                / ".modus_capture_session.json"
            )

            payload = json.loads(
                session_path.read_text(encoding="utf-8")
            )
            first_item = payload["items"][0]

            Path(
                batch.next_item.destination_folder,
                first_item["destination_filename"],
            ).write_text(
                "<html>captured match</html>",
                encoding="utf-8",
            )

            refreshed = self.service.load(root)

        self.assertEqual(refreshed.processed_matches, 1)
        self.assertNotEqual(
            refreshed.current_match_id,
            started.current_match_id,
        )
        self.assertIn(
            "advanced",
            refreshed.last_message.lower(),
        )

    def test_clear_removes_only_runner_state(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.create_batch(root)
            self.service.start(root)

            self.assertTrue(self.service.clear(root))
            self.assertFalse(
                Path(root, RUNNER_FILENAME).exists()
            )
            self.assertTrue(
                Path(
                    root,
                    ".dartsedge_capture_batch.json",
                ).exists()
            )
            self.assertTrue(
                (
                    batch.next_item.destination_folder
                    / ".modus_capture_session.json"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
