import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.services.live_edge_monitor_service import (
    live_edge_monitor,
)
from app.services.model_trust_monitor_service import (
    model_trust_monitor,
)
from app.services.sparse_consensus_risk_monitor_service import (
    sparse_consensus_risk_monitor,
)


class ApplicationMonitorLifecycleTests(unittest.TestCase):
    def test_background_monitors_follow_application_lifecycle(self):
        monitors = (
            live_edge_monitor,
            forward_schedule_monitor,
            model_trust_monitor,
            sparse_consensus_risk_monitor,
        )

        with ExitStack() as stack:
            start_mocks = [
                stack.enter_context(
                    patch.object(monitor, "start")
                )
                for monitor in monitors
            ]
            stop_mocks = [
                stack.enter_context(
                    patch.object(monitor, "stop")
                )
                for monitor in monitors
            ]

            for mock in start_mocks:
                mock.assert_not_called()

            for mock in stop_mocks:
                mock.assert_not_called()

            with TestClient(app):
                for mock in start_mocks:
                    mock.assert_called_once_with()

                for mock in stop_mocks:
                    mock.assert_not_called()

            for mock in stop_mocks:
                mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
