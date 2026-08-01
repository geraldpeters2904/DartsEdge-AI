import unittest

from app.services.historical_capture_engine import (
    HistoricalCaptureEngine,
)


class HistoricalCaptureEngineTests(unittest.TestCase):

    def test_engine_exists(self):
        engine = HistoricalCaptureEngine()

        self.assertIsNotNone(engine)

    def test_iteration_not_implemented_yet(self):
        engine = HistoricalCaptureEngine()

        with self.assertRaises(NotImplementedError):
            engine.run_iteration("/tmp")


if __name__ == "__main__":
    unittest.main()