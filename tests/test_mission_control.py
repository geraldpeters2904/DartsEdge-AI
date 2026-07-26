import unittest

from app.db import SessionLocal
from app.services.mission_control_service import build_mission_control_data


class MissionControlServiceTests(unittest.TestCase):
    def test_payload_contains_required_sections(self):
        db = SessionLocal()
        try:
            result = build_mission_control_data(db)
        finally:
            db.close()

        required_keys = {
            "ranked_opportunities",
            "opportunity_count",
            "open_stake",
            "exposure_percent",
            "model_health",
            "alerts",
            "ai_coach",
            "current_bankroll",
            "winner_accuracy",
        }

        self.assertTrue(required_keys.issubset(result.keys()))
        self.assertIsInstance(result["ranked_opportunities"], list)
        self.assertIsInstance(result["alerts"], list)
        self.assertGreaterEqual(len(result["alerts"]), 1)
        self.assertEqual(len(result["model_health"]), 3)


if __name__ == "__main__":
    unittest.main()
