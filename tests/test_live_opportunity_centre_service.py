import unittest
from datetime import datetime, timedelta

from app.services.live_opportunity_centre_service import _state


class LiveOpportunityLifecycleTests(unittest.TestCase):
    def test_new_state(self):
        self.assertEqual(
            _state(
                current_score=75,
                first_score=75,
                peak_score=75,
                age_minutes=5,
            ),
            "NEW",
        )

    def test_peak_state(self):
        self.assertEqual(
            _state(
                current_score=92,
                first_score=80,
                peak_score=92,
                age_minutes=30,
            ),
            "PEAK",
        )

    def test_mature_state(self):
        self.assertEqual(
            _state(
                current_score=84,
                first_score=80,
                peak_score=86,
                age_minutes=35,
            ),
            "MATURE",
        )

    def test_declining_state(self):
        self.assertEqual(
            _state(
                current_score=74,
                first_score=80,
                peak_score=85,
                age_minutes=40,
            ),
            "DECLINING",
        )


if __name__ == "__main__":
    unittest.main()
