import unittest
from unittest.mock import Mock, patch

from app.services import forward_fixture_catchup_runner


class ForwardFixtureCatchupRunnerTests(unittest.TestCase):

    @patch(
        "app.services.forward_fixture_catchup_runner."
        "run_forward_fixture_catchup"
    )
    @patch(
        "app.services.forward_fixture_catchup_runner."
        "SessionLocal"
    )
    def test_success_commits_and_closes(
        self,
        session_local,
        run_catchup,
    ):
        db = Mock()
        session_local.return_value = db
        expected = object()
        run_catchup.return_value = expected

        result = forward_fixture_catchup_runner.run_once()

        self.assertIs(result, expected)
        run_catchup.assert_called_once_with(db)
        db.commit.assert_called_once_with()
        db.rollback.assert_not_called()
        db.close.assert_called_once_with()

    @patch(
        "app.services.forward_fixture_catchup_runner."
        "run_forward_fixture_catchup"
    )
    @patch(
        "app.services.forward_fixture_catchup_runner."
        "SessionLocal"
    )
    def test_failure_rolls_back_and_closes(
        self,
        session_local,
        run_catchup,
    ):
        db = Mock()
        session_local.return_value = db
        run_catchup.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            forward_fixture_catchup_runner.run_once()

        db.commit.assert_not_called()
        db.rollback.assert_called_once_with()
        db.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
