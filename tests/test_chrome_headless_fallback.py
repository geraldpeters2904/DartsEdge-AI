import unittest

from app.services.chrome_browser_session import ChromeBrowserSession


class _FakeDriver:
    def quit(self):
        pass


class ChromeHeadlessFallbackTests(unittest.TestCase):
    def test_headless_startup_falls_back_to_visible(self):
        session = ChromeBrowserSession(
            headless=True,
        )

        calls = []

        def create():
            calls.append(session._headless)

            if session._headless:
                raise RuntimeError(
                    "session not created from chrome not reachable"
                )

            return _FakeDriver()

        session._create_chrome_driver = create

        try:
            session.open()

            self.assertTrue(
                session.running
            )

            self.assertEqual(
                calls,
                [
                    True,
                    False,
                ],
            )

            self.assertFalse(
                session._headless
            )
        finally:
            session.close()

    def test_non_headless_failure_is_not_retried(self):
        session = ChromeBrowserSession(
            headless=False,
        )

        calls = []

        def create():
            calls.append(True)
            raise RuntimeError(
                "chrome startup failure"
            )

        session._create_chrome_driver = create

        with self.assertRaises(
            RuntimeError
        ):
            session.open()

        self.assertEqual(
            len(calls),
            1,
        )


if __name__ == "__main__":
    unittest.main()
