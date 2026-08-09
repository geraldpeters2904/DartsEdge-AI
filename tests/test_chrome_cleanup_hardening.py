import unittest

from app.services.chrome_browser_session import ChromeBrowserSession


class FakeProcess:
    def __init__(self):
        self.alive = True
        self.terminated = False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.terminated = True
        self.alive = False

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.alive = False


class FakeService:
    def __init__(self, process):
        self.process = process


class FakeDriver:
    def __init__(self, process, quit_raises=False):
        self.service = FakeService(process)
        self.quit_raises = quit_raises

    def quit(self):
        if self.quit_raises:
            raise RuntimeError("quit failed")


class ChromeCleanupHardeningTests(unittest.TestCase):
    def test_close_terminates_service_process(self):
        process = FakeProcess()
        session = ChromeBrowserSession()
        session._driver = FakeDriver(process)
        session.close()
        self.assertTrue(process.terminated)
        self.assertFalse(process.alive)

    def test_close_terminates_process_even_if_quit_fails(self):
        process = FakeProcess()
        session = ChromeBrowserSession()
        session._driver = FakeDriver(process, quit_raises=True)
        session.close()
        self.assertTrue(process.terminated)
        self.assertFalse(process.alive)


if __name__ == "__main__":
    unittest.main()
