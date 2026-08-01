import unittest
from pathlib import Path

from app.services.historical_runner_service import (
    HistoricalRunnerState,
)
from app.services.historical_workflow_service import (
    HistoricalWorkflowService,
)
from app.services.modus_capture_assistant_service import (
    CaptureAssistantStatus,
)


GROUP_A = "/tmp/history/Series_14/Week_01/Group_A"
GROUP_B = "/tmp/history/Series_14/Week_01/Group_B"


def runner_state(
    status="stopped",
    destination=None,
    match_id=None,
):
    return HistoricalRunnerState(
        root=Path("/tmp/history"),
        status=status,
        created_at="2026-07-31T12:00:00",
        updated_at="2026-07-31T12:00:00",
        started_at=None,
        paused_at=None,
        stopped_at=None,
        completed_at=(
            "2026-07-31T13:00:00"
            if status == "completed"
            else None
        ),
        current_position=1 if destination else None,
        current_series_id=14 if destination else None,
        current_series_label=(
            "Series 14" if destination else None
        ),
        current_week_id=165 if destination else None,
        current_week_label=(
            "Week 1" if destination else None
        ),
        current_group=(
            Path(destination).name.replace("_", " ")
            if destination
            else None
        ),
        current_match_id=match_id,
        current_destination_folder=destination,
        processed_matches=0,
        remaining_matches=45,
        total_matches=45,
        last_message="Test runner state.",
        last_error=None,
    )


def assistant_status(
    running=False,
    destination="",
    watch_folder="",
):
    return CaptureAssistantStatus(
        running=running,
        destination_folder=destination,
        watch_folder=watch_folder,
        expected_match_id=None,
        expected_filename=None,
        accepted_count=0,
        rejected_count=0,
        last_message="Test assistant state.",
        events=[],
    )


class FakeRunnerService:
    def __init__(self):
        self.state = runner_state()
        self.failed_error = None

    def load(self, root):
        return self.state

    def start(self, root):
        self.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        return self.state

    def pause(self, root):
        self.state = runner_state(
            status="paused",
            destination=GROUP_A,
            match_id=16947,
        )
        return self.state

    def resume(self, root):
        self.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        return self.state

    def stop(self, root):
        self.state = runner_state(
            status="stopped",
            destination=GROUP_A,
            match_id=16947,
        )
        return self.state

    def mark_failed(self, root, error):
        self.failed_error = error
        self.state = runner_state(
            status="failed",
            destination=GROUP_A,
            match_id=16947,
        )
        return self.state


class FakeAssistantService:
    def __init__(self):
        self.running = False
        self.destination = ""
        self.watch_folder = ""
        self.started_with = None
        self.start_count = 0
        self.stop_count = 0
        self.start_error = None

    def status(self):
        return assistant_status(
            running=self.running,
            destination=self.destination,
            watch_folder=self.watch_folder,
        )

    def start(self, destination_folder, watch_folder):
        if self.start_error:
            raise ValueError(self.start_error)

        self.started_with = (
            destination_folder,
            watch_folder,
        )
        self.destination = destination_folder
        self.watch_folder = watch_folder
        self.running = True
        self.start_count += 1
        return self.status()

    def stop(self):
        self.running = False
        self.stop_count += 1
        return self.status()


class HistoricalWorkflowServiceTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunnerService()
        self.assistant = FakeAssistantService()
        self.service = HistoricalWorkflowService(
            runner_service=self.runner,
            assistant_service=self.assistant,
        )

    def test_start_coordinates_runner_and_assistant(self):
        status = self.service.start(
            "/tmp/history",
            watch_folder="/tmp/downloads",
        )

        self.assertTrue(status.running)
        self.assertTrue(status.assistant.running)
        self.assertEqual(status.current_match_id, 16947)
        self.assertEqual(
            self.assistant.started_with,
            (GROUP_A, "/tmp/downloads"),
        )

    def test_pause_pauses_runner_and_stops_assistant(self):
        self.service.start("/tmp/history")
        status = self.service.pause("/tmp/history")

        self.assertTrue(status.paused)
        self.assertFalse(status.assistant.running)
        self.assertEqual(self.assistant.stop_count, 1)

    def test_resume_restarts_assistant(self):
        self.service.start("/tmp/history")
        self.service.pause("/tmp/history")

        status = self.service.resume(
            "/tmp/history",
            watch_folder="/tmp/downloads",
        )

        self.assertTrue(status.running)
        self.assertTrue(status.assistant.running)
        self.assertEqual(
            self.assistant.started_with[1],
            "/tmp/downloads",
        )

    def test_stop_stops_runner_and_assistant(self):
        self.service.start("/tmp/history")
        status = self.service.stop("/tmp/history")

        self.assertTrue(status.stopped)
        self.assertFalse(status.assistant.running)

    def test_assistant_start_failure_marks_runner_failed(self):
        self.assistant.start_error = "Watch folder unavailable"

        with self.assertRaisesRegex(
            ValueError,
            "Watch folder unavailable",
        ):
            self.service.start("/tmp/history")

        self.assertEqual(
            self.runner.failed_error,
            "Watch folder unavailable",
        )
        self.assertEqual(self.runner.state.status, "failed")

    def test_synchronise_moves_assistant_to_new_group(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_B,
            match_id=17001,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        status = self.service.synchronise("/tmp/history")

        self.assertTrue(status.running)
        self.assertTrue(status.assistant.running)
        self.assertEqual(
            self.assistant.started_with,
            (GROUP_B, "/tmp/downloads"),
        )
        self.assertEqual(self.assistant.start_count, 1)

    def test_synchronise_restarts_stopped_assistant(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = False
        self.assistant.watch_folder = "/tmp/downloads"

        status = self.service.synchronise("/tmp/history")

        self.assertTrue(status.assistant.running)
        self.assertEqual(
            self.assistant.started_with,
            (GROUP_A, "/tmp/downloads"),
        )

    def test_synchronise_does_not_restart_correct_assistant(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16948,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        status = self.service.synchronise("/tmp/history")

        self.assertTrue(status.assistant.running)
        self.assertEqual(self.assistant.start_count, 0)

    def test_synchronise_stops_assistant_at_completion(self):
        self.runner.state = runner_state(
            status="completed",
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        status = self.service.synchronise("/tmp/history")

        self.assertTrue(status.runner.complete)
        self.assertFalse(status.assistant.running)
        self.assertEqual(self.assistant.stop_count, 1)


if __name__ == "__main__":
    unittest.main()
