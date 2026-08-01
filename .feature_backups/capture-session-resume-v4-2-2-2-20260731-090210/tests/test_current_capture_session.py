import tempfile
import time
import unittest
from pathlib import Path

from app.services.current_capture_session_service import CurrentCaptureSessionService
from app.services.modus_capture_session_service import ModusCaptureSessionService

FIXTURE = Path('tests/fixtures/modus_capture/series14_week01_group_a.html')


class CurrentCaptureSessionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(encoding='utf-8')

    def setUp(self):
        self.session_service = ModusCaptureSessionService()
        self.service = CurrentCaptureSessionService()

    def test_returns_latest_incomplete_session(self):
        with tempfile.TemporaryDirectory() as root:
            first = Path(root, 'first')
            second = Path(root, 'second')
            self.session_service.create_session(
                results_filename='first.html',
                results_html=self.results_html,
                destination_folder=first,
            )
            time.sleep(0.02)
            self.session_service.create_session(
                results_filename='second.html',
                results_html=self.results_html,
                destination_folder=second,
            )
            latest = self.service.latest_incomplete(root)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.folder.name, 'second')

    def test_returns_none_when_no_sessions_exist(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(self.service.latest_incomplete(root))


if __name__ == '__main__':
    unittest.main()
