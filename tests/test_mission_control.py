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


class MissionControlModelHealthIntegrationTests(unittest.TestCase):
    def test_prediction_model_health_is_included_without_replacing_operating_indicators(self):
        from unittest.mock import patch
        from types import SimpleNamespace

        service = "app.services.mission_control_service"
        dashboard = {
            "winner_accuracy": 70,
            "database_health": 90,
            "results_awaiting": [],
            "open_paper_trades": 0,
        }
        portfolio = {
            "health_score": 85,
            "open_exposure": 0,
            "exposure_percent": 0,
        }
        report = SimpleNamespace(
            model_name="Player Intelligence",
            model_version="v1",
            health_score=78,
            health_grade="Good",
            recommendation="Continue monitoring",
            warnings=("Insufficient model-linked trading history",),
        )

        with (
            patch(f"{service}.build_dashboard_data", return_value=dashboard),
            patch(f"{service}.build_ranked_opportunities", return_value=[]),
            patch(f"{service}.build_portfolio_health", return_value=portfolio),
            patch(f"{service}.build_ai_coach_data", return_value={
                "primary": {"headline": "No action"},
                "recommendation_count": 0,
            }),
            patch(f"{service}.get_active_strategy", return_value=object()),
            patch(f"{service}.strategy_summary", return_value={
                "enforcement_mode": "shadow",
                "decision_rules_enabled": False,
            }),
            patch(f"{service}.build_model_health", return_value=report, create=True),
            patch(f"{service}.model_health_summary", return_value={
                "model_name": report.model_name,
                "model_version": report.model_version,
                "health_score": report.health_score,
                "health_grade": report.health_grade,
                "recommendation": report.recommendation,
                "warnings": list(report.warnings),
            }, create=True),
        ):
            from app.services.mission_control_service import build_mission_control_data
            result = build_mission_control_data(object())

        self.assertEqual(len(result["model_health"]), 3)
        self.assertEqual(result["prediction_model_health"]["health_score"], 78)
        self.assertEqual(result["prediction_model_health"]["model_version"], "v1")
        self.assertIn("Insufficient model-linked trading history",
                      result["prediction_model_health"]["warnings"])


    def test_prediction_model_health_failure_does_not_break_mission_control(self):
        from unittest.mock import patch

        service = "app.services.mission_control_service"
        dashboard = {
            "winner_accuracy": 70,
            "database_health": 90,
            "results_awaiting": [],
            "open_paper_trades": 0,
        }
        portfolio = {
            "health_score": 85,
            "open_exposure": 0,
            "exposure_percent": 0,
        }

        with (
            patch(f"{service}.build_dashboard_data", return_value=dashboard),
            patch(f"{service}.build_ranked_opportunities", return_value=[]),
            patch(f"{service}.build_portfolio_health", return_value=portfolio),
            patch(f"{service}.build_ai_coach_data", return_value={
                "primary": {"headline": "No action"},
                "recommendation_count": 0,
            }),
            patch(f"{service}.get_active_strategy", return_value=object()),
            patch(f"{service}.strategy_summary", return_value={
                "enforcement_mode": "shadow",
                "decision_rules_enabled": False,
            }),
            patch(
                f"{service}.build_model_health",
                side_effect=RuntimeError("Model health unavailable"),
                create=True,
            ),
        ):
            from app.services.mission_control_service import build_mission_control_data
            result = build_mission_control_data(object())

        self.assertEqual(len(result["model_health"]), 3)
        self.assertEqual(result["winner_accuracy"], 70)
        self.assertIn("prediction_model_health", result)
        self.assertIsNone(result["prediction_model_health"])


if __name__ == "__main__":
    unittest.main()
