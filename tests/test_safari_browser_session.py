import unittest

from app.services.safari_browser_session import (
    SafariBrowserSession,
)


class FakeSafariDriver:
    def __init__(self):
        self.page_source = (
            "<html><head><title>Test</title></head>"
            "<body>Match page</body></html>"
        )
        self.title = "Test Match"
        self.current_url = ""
        self.timeout = None
        self.get_calls = []
        self.quit_calls = 0
        self.ready_state = "complete"

    def set_page_load_timeout(self, timeout):
        self.timeout = timeout

    def get(self, url):
        self.current_url = url
        self.get_calls.append(url)

    def execute_script(self, script):
        return self.ready_state

    def quit(self):
        self.quit_calls += 1


class SafariBrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.driver = FakeSafariDriver()
        self.session = SafariBrowserSession(
            driver_factory=lambda: self.driver,
            poll_interval_seconds=0.001,
        )

    def tearDown(self):
        self.session.close()

    def test_open_is_idempotent(self):
        self.session.open()
        self.session.open()

        self.assertTrue(self.session.running)

    def test_goto_opens_browser_and_loads_url(self):
        self.session.goto(
            "https://example.test/match/16954",
            timeout_seconds=5,
        )

        self.assertTrue(self.session.running)
        self.assertEqual(
            self.driver.get_calls,
            ["https://example.test/match/16954"],
        )
        self.assertEqual(self.driver.timeout, 5)

    def test_reads_current_page_details(self):
        self.session.goto(
            "https://example.test/match/16954"
        )

        self.assertIn(
            "Match page",
            self.session.html(),
        )
        self.assertEqual(
            self.session.title(),
            "Test Match",
        )
        self.assertEqual(
            self.session.current_url(),
            "https://example.test/match/16954",
        )

    def test_rejects_invalid_url(self):
        with self.assertRaisesRegex(
            ValueError,
            "HTTP or HTTPS",
        ):
            self.session.goto("file:///tmp/page.html")

    def test_access_before_open_is_rejected(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "not running",
        ):
            self.session.html()

    def test_close_quits_browser(self):
        self.session.open()
        self.session.close()

        self.assertFalse(self.session.running)
        self.assertEqual(self.driver.quit_calls, 1)

    def test_context_manager_closes_browser(self):
        with SafariBrowserSession(
            driver_factory=lambda: self.driver,
        ) as session:
            self.assertTrue(session.running)

        self.assertEqual(self.driver.quit_calls, 1)


if __name__ == "__main__":
    unittest.main()
