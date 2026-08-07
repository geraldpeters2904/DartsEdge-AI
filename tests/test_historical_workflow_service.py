import unittest
from pathlib import Path

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.historical_capture_config import (
    HistoricalCaptureConfig,
)
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


class FakeDatabaseSession:
    def __init__(self):
        self.closed = False
        self.rolled_back = False

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True


class FakeHistoryService:
    def __init__(self):
        self.calls = []

    def record(self, db, **kwargs):
        self.calls.append(
            {
                "db": db,
                **kwargs,
            }
        )
        return kwargs


class FakeCaptureConfigService:
    def __init__(self, provider="manual"):
        self.provider = provider
        self.loaded_root = None

    def load(self, root):
        self.loaded_root = root
        return HistoricalCaptureConfig(
            provider=self.provider,
        )


class FakeCaptureSessionService:
    def __init__(self):
        self.request = None
        self.destination = None

    def next_capture_request(self, destination):
        self.destination = destination
        return self.request


class FakeCaptureExecutor:
    def __init__(self):
        self.result = None
        self.results = []
        self.request = None
        self.provider_name = None
        self.on_execute = None
        self.execute_count = 0

    def execute(self, request, *, provider_name):
        self.request = request
        self.provider_name = provider_name
        self.execute_count += 1

        result = (
            self.results.pop(0)
            if self.results
            else self.result
        )

        if result is None:
            raise AssertionError(
                "Fake capture executor has no configured result."
            )

        if self.on_execute is not None:
            self.on_execute()

        return result


class HistoricalWorkflowServiceTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunnerService()
        self.assistant = FakeAssistantService()
        self.capture_session = FakeCaptureSessionService()
        self.capture_executor = FakeCaptureExecutor()
        self.history = FakeHistoryService()
        self.database_sessions = []

        def create_database_session():
            session = FakeDatabaseSession()
            self.database_sessions.append(session)
            return session

        self.service = HistoricalWorkflowService(
            runner_service=self.runner,
            assistant_service=self.assistant,
            capture_session_service=self.capture_session,
            capture_executor=self.capture_executor,
            capture_provider_name="fake",
            history_service=self.history,
            db_session_factory=create_database_session,
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


    def test_capture_iteration_records_success_summary(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        status = self.service.capture_iteration("/tmp/history")
        summary = self.service.last_capture_summary

        self.assertTrue(status.running)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.status, "running")
        self.assertEqual(summary.errors, 0)
        self.assertIsNotNone(summary.finished_at)
        self.assertIsNotNone(summary.duration_seconds)

    def test_capture_iteration_records_failure_summary(self):
        self.runner.state = runner_state(
            status="running",
            destination=None,
            match_id=16947,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Historical runner has no current capture folder",
        ):
            self.service.capture_iteration("/tmp/history")

        summary = self.service.last_capture_summary

        self.assertIsNotNone(summary)
        self.assertEqual(summary.status, "failed")
        self.assertEqual(summary.errors, 1)
        self.assertIsNotNone(summary.finished_at)
        self.assertIsNotNone(summary.duration_seconds)


    def test_latest_capture_summary_returns_recorded_summary(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        self.service.capture_iteration("/tmp/history")

        summary = self.service.latest_capture_summary()

        self.assertIsNotNone(summary)
        self.assertIs(
            summary,
            self.service.last_capture_summary,
        )


    def test_capture_iteration_executes_next_capture_request(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.result = CaptureResult(
            provider="fake",
            status="captured",
            match_id=16947,
            destination_path=request.destination_path,
            message="Capture completed.",
            bytes_written=2048,
        )

        status = self.service.capture_iteration("/tmp/history")
        summary = self.service.latest_capture_summary()

        self.assertTrue(status.running)
        self.assertIs(
            self.capture_executor.request,
            request,
        )
        self.assertEqual(
            self.capture_executor.provider_name,
            "fake",
        )
        self.assertEqual(summary.matches_captured, 1)
        self.assertEqual(summary.bytes_written, 2048)
        self.assertEqual(summary.errors, 0)


    def test_capture_iteration_records_waiting_result(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.result = CaptureResult(
            provider="fake",
            status="waiting",
            match_id=16947,
            destination_path=None,
            message="Waiting for capture.",
        )

        status = self.service.capture_iteration("/tmp/history")
        summary = self.service.latest_capture_summary()

        self.assertTrue(status.running)
        self.assertEqual(summary.captures_waiting, 1)
        self.assertEqual(summary.matches_captured, 0)
        self.assertEqual(summary.bytes_written, 0)
        self.assertEqual(summary.errors, 0)

    def test_capture_iteration_raises_provider_failure(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.result = CaptureResult(
            provider="fake",
            status="failed",
            match_id=16947,
            destination_path=None,
            message="Capture failed.",
            error="Provider unavailable.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Provider unavailable",
        ):
            self.service.capture_iteration("/tmp/history")

        summary = self.service.latest_capture_summary()

        self.assertEqual(summary.status, "failed")
        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.matches_captured, 0)
        self.assertEqual(summary.bytes_written, 0)


    def test_successful_capture_advances_runner_to_next_match(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.result = CaptureResult(
            provider="fake",
            status="captured",
            match_id=16947,
            destination_path=request.destination_path,
            message="Capture completed.",
            bytes_written=2048,
        )

        def advance_runner():
            self.runner.state = runner_state(
                status="running",
                destination=GROUP_A,
                match_id=16948,
            )

        self.capture_executor.on_execute = advance_runner

        status = self.service.capture_iteration("/tmp/history")
        summary = self.service.latest_capture_summary()

        self.assertTrue(status.running)
        self.assertEqual(status.current_match_id, 16948)
        self.assertEqual(summary.matches_captured, 1)
        self.assertEqual(summary.bytes_written, 2048)
        self.assertEqual(summary.errors, 0)


    def test_capture_iteration_uses_configured_provider(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )

        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )

        capture_session = FakeCaptureSessionService()
        capture_session.request = request

        capture_executor = FakeCaptureExecutor()
        capture_executor.result = CaptureResult(
            provider="safari",
            status="waiting",
            match_id=16947,
            destination_path=None,
            message="Waiting.",
        )

        config_service = FakeCaptureConfigService(
            provider="safari",
        )

        service = HistoricalWorkflowService(
            runner_service=self.runner,
            assistant_service=self.assistant,
            capture_session_service=capture_session,
            capture_executor=capture_executor,
            capture_config_service=config_service,
        )

        service.capture_iteration("/tmp/history")

        self.assertEqual(
            capture_executor.provider_name,
            "safari",
        )
        self.assertEqual(
            config_service.loaded_root,
            "/tmp/history",
        )


    def test_capture_iteration_retries_then_succeeds(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )

        self.capture_session.request = request
        self.capture_executor.results = [
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Temporary failure.",
                error="Temporary failure.",
            ),
            CaptureResult(
                provider="fake",
                status="captured",
                match_id=16947,
                destination_path=request.destination_path,
                message="Capture completed.",
                bytes_written=4096,
            ),
        ]

        config_service = FakeCaptureConfigService(
            provider="manual",
        )
        sleep_calls = []

        service = HistoricalWorkflowService(
            runner_service=self.runner,
            assistant_service=self.assistant,
            capture_session_service=self.capture_session,
            capture_executor=self.capture_executor,
            capture_config_service=config_service,
            capture_provider_name="fake",
            sleep_fn=sleep_calls.append,
        )

        service.capture_iteration("/tmp/history")
        summary = service.latest_capture_summary()

        self.assertEqual(
            self.capture_executor.execute_count,
            2,
        )
        self.assertEqual(sleep_calls, [5.0])
        self.assertEqual(summary.matches_captured, 1)
        self.assertEqual(summary.bytes_written, 4096)
        self.assertEqual(summary.retries_attempted, 1)
        self.assertEqual(summary.errors, 0)

    def test_capture_iteration_fails_after_retry_limit(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )

        self.capture_session.request = request
        self.capture_executor.results = [
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Failure 1.",
                error="Provider unavailable.",
            ),
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Failure 2.",
                error="Provider unavailable.",
            ),
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Failure 3.",
                error="Provider unavailable.",
            ),
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Failure 4.",
                error="Provider unavailable.",
            ),
        ]

        sleep_calls = []

        service = HistoricalWorkflowService(
            runner_service=self.runner,
            assistant_service=self.assistant,
            capture_session_service=self.capture_session,
            capture_executor=self.capture_executor,
            capture_config_service=FakeCaptureConfigService(),
            capture_provider_name="fake",
            sleep_fn=sleep_calls.append,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Provider unavailable",
        ):
            service.capture_iteration("/tmp/history")

        summary = service.latest_capture_summary()

        self.assertEqual(
            self.capture_executor.execute_count,
            4,
        )
        self.assertEqual(
            sleep_calls,
            [5.0, 5.0, 5.0],
        )
        self.assertEqual(summary.retries_attempted, 3)
        self.assertEqual(summary.errors, 1)
        self.assertEqual(summary.status, "failed")


    def test_capture_iteration_records_success_history(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.result = CaptureResult(
            provider="fake",
            status="captured",
            match_id=16947,
            destination_path=request.destination_path,
            message="Capture completed.",
            bytes_written=7004,
        )

        self.service.capture_iteration("/tmp/history")

        self.assertEqual(len(self.history.calls), 1)

        call = self.history.calls[0]

        self.assertEqual(
            call["capture_root"],
            "/tmp/history",
        )
        self.assertEqual(call["provider"], "fake")
        self.assertEqual(call["match_id"], 16947)
        self.assertEqual(
            call["summary"].matches_captured,
            1,
        )
        self.assertEqual(
            call["summary"].bytes_written,
            7004,
        )
        self.assertIsNone(call["error_detail"])
        self.assertTrue(call["db"].closed)

    def test_capture_iteration_records_failure_history(self):
        self.runner.state = runner_state(
            status="running",
            destination=GROUP_A,
            match_id=16947,
        )
        self.assistant.running = True
        self.assistant.destination = GROUP_A
        self.assistant.watch_folder = "/tmp/downloads"

        request = CaptureRequest(
            match_id=16947,
            source_url="https://example.test/match/16947",
            destination_folder=Path(GROUP_A),
            destination_filename="match_16947.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )
        self.capture_session.request = request
        self.capture_executor.results = [
            CaptureResult(
                provider="fake",
                status="failed",
                match_id=16947,
                destination_path=None,
                message="Capture failed.",
                error="Provider unavailable.",
            )
            for _ in range(4)
        ]

        self.service.sleep_fn = lambda seconds: None

        with self.assertRaisesRegex(
            ValueError,
            "Provider unavailable",
        ):
            self.service.capture_iteration("/tmp/history")

        self.assertEqual(len(self.history.calls), 1)

        call = self.history.calls[0]

        self.assertEqual(call["provider"], "fake")
        self.assertEqual(call["match_id"], 16947)
        self.assertEqual(call["summary"].status, "failed")
        self.assertEqual(call["summary"].errors, 1)
        self.assertEqual(
            call["summary"].retries_attempted,
            3,
        )
        self.assertEqual(
            call["error_detail"],
            "Provider unavailable.",
        )
        self.assertTrue(call["db"].closed)


if __name__ == "__main__":
    unittest.main()
