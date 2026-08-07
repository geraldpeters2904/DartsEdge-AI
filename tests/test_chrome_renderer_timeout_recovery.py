import unittest

from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)


class TimeoutDriver:
    def __init__(self):
        self.closed = False

    def set_page_load_timeout(self, value):
        pass

    def get(self, url):
        raise RuntimeError(
            "timeout: Timed out receiving message from renderer"
        )

    def quit(self):
        self.closed = True


class GoodDriver:
    def __init__(self):
        self.urls = []
        self.closed = False

    def set_page_load_timeout(self, value):
        pass

    def get(self, url):
        self.urls.append(url)

    def execute_script(self, script):
        return "complete"

    def quit(self):
        self.closed = True


class ChromeRendererTimeoutRecoveryTests(unittest.TestCase):
    def test_reopens_after_renderer_timeout(self):
        timed_out = TimeoutDriver()
        good = GoodDriver()
        drivers = [timed_out, good]

        session = ChromeBrowserSession(
            driver_factory=lambda: drivers.pop(0),
            poll_interval_seconds=0.01,
        )

        session.goto(
            "https://example.test/results",
            timeout_seconds=1,
        )

        self.assertTrue(timed_out.closed)
        self.assertEqual(
            good.urls,
            ["https://example.test/results"],
        )
        self.assertTrue(session.running)

        session.close()


if __name__ == "__main__":
    unittest.main()
