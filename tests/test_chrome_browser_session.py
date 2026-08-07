import tempfile
import unittest
from pathlib import Path

from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)


class FakeDriver:
    def __init__(self):
        self.page_source = "<html>MODUS</html>"
        self.title = "MODUS Results"
        self.current_url = "https://example.test/results"
        self.closed = False
        self.urls = []
        self.timeout = None

    def set_page_load_timeout(self, value):
        self.timeout = value

    def get(self, url):
        self.urls.append(url)

    def execute_script(self, script):
        return "complete"

    def quit(self):
        self.closed = True


class ChromeBrowserSessionTests(unittest.TestCase):
    def test_reuses_one_dedicated_driver(self):
        driver = FakeDriver()
        calls = []

        def factory():
            calls.append(True)
            return driver

        session = ChromeBrowserSession(
            driver_factory=factory,
        )

        session.goto("https://example.test/results")
        session.goto("https://example.test/match")

        self.assertTrue(session.running)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            driver.urls,
            [
                "https://example.test/results",
                "https://example.test/match",
            ],
        )

    def test_exposes_rendered_page_details(self):
        driver = FakeDriver()
        session = ChromeBrowserSession(
            driver_factory=lambda: driver,
        )
        session.open()

        self.assertEqual(
            session.html(),
            "<html>MODUS</html>",
        )
        self.assertEqual(
            session.title(),
            "MODUS Results",
        )
        self.assertEqual(
            session.current_url(),
            "https://example.test/results",
        )

    def test_close_quits_driver(self):
        driver = FakeDriver()
        session = ChromeBrowserSession(
            driver_factory=lambda: driver,
        )
        session.open()
        session.close()

        self.assertFalse(session.running)
        self.assertTrue(driver.closed)

    def test_profile_folder_is_removed_on_close(self):
        with tempfile.TemporaryDirectory() as root:
            session = ChromeBrowserSession(
                driver_factory=lambda: FakeDriver(),
                profile_root=root,
            )
            # Exercise profile management without real Selenium.
            profile = session._create_profile_path()
            self.assertTrue(profile.exists())

            session.close()

            self.assertFalse(profile.exists())

    def test_invalid_url_is_rejected(self):
        session = ChromeBrowserSession(
            driver_factory=lambda: FakeDriver(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "HTTP or HTTPS",
        ):
            session.goto("file:///tmp/results.html")


if __name__ == "__main__":
    unittest.main()
