import unittest

from app.services.chrome_browser_session import ChromeBrowserSession


class LostDriver:
    def __init__(self):
        self.closed = False

    def set_page_load_timeout(self, value):
        pass

    def get(self, url):
        raise RuntimeError(
            "invalid session id: session deleted as the browser has closed the connection"
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


class ChromeSessionRecoveryTests(unittest.TestCase):
    def test_reopens_browser_after_lost_session(self):
        lost = LostDriver()
        good = GoodDriver()
        drivers = [lost, good]

        session = ChromeBrowserSession(
            driver_factory=lambda: drivers.pop(0),
            poll_interval_seconds=0.01,
        )

        session.goto("https://example.test/results", timeout_seconds=1)

        self.assertTrue(lost.closed)
        self.assertEqual(good.urls, ["https://example.test/results"])
        self.assertTrue(session.running)
        session.close()

    def test_non_session_error_is_not_retried(self):
        class BrokenDriver:
            def set_page_load_timeout(self, value):
                pass

            def get(self, url):
                raise RuntimeError("DNS lookup failed")

            def quit(self):
                pass

        calls = []

        def factory():
            calls.append(True)
            return BrokenDriver()

        session = ChromeBrowserSession(driver_factory=factory)

        with self.assertRaisesRegex(RuntimeError, "DNS lookup failed"):
            session.goto("https://example.test")

        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
