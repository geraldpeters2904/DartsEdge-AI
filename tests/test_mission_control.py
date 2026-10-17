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



    def test_prediction_model_health_uses_background_trust_report(self):
        from unittest.mock import patch
        from types import SimpleNamespace

        service = "app.services.mission_control_service"
        cached = SimpleNamespace(
            model_name="Player Intelligence",
            model_version="transparent-v3.5",
            trust_score=77,
            trust_grade="High",
        )
        captured = {}

        def fake_model_health(db, **kwargs):
            captured.update(kwargs)
            trust = kwargs["trust_builder"](
                db,
                model_name="Player Intelligence",
                offset=500,
                limit=3000,
            )
            self.assertIs(trust, cached)
            return SimpleNamespace(
                health_score=83,
                model_version=trust.model_version,
            )

        with (
            patch(f"{service}.build_dashboard_data", return_value={
                "winner_accuracy": 70,
                "database_health": 90,
                "results_awaiting": [],
                "open_paper_trades": 0,
            }),
            patch(f"{service}.build_ranked_opportunities", return_value=[]),
            patch(f"{service}.build_portfolio_health", return_value={
                "health_score": 85,
                "open_exposure": 0,
                "exposure_percent": 0,
            }),
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
                "app.services.model_trust_monitor_service."
                "model_trust_monitor.latest_report",
                return_value=cached,
            ) as latest,
            patch(f"{service}.build_model_health", side_effect=fake_model_health),
            patch(f"{service}.model_health_summary", return_value={
                "health_score": 83,
                "model_version": "transparent-v3.5",
            }),
        ):
            from app.services.mission_control_service import build_mission_control_data
            result = build_mission_control_data(object())

        self.assertEqual(result["prediction_model_health"]["health_score"], 83)
        self.assertIn("trust_builder", captured)
        latest.assert_called_once_with()

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



class MissionControlDataReuseTests(unittest.TestCase):
    def test_ai_coach_reuses_mission_control_inputs(self):
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
        strategy = {
            "enforcement_mode": "shadow",
            "decision_rules_enabled": False,
        }
        opportunities = [
            {"selection": f"Player {i}"} for i in range(20)
        ]
        coach_calls = []

        def fake_ranked(db, *, limit, prediction_contexts=None):
            return opportunities[:limit]

        def fake_coach(db, **kwargs):
            coach_calls.append(kwargs)
            return {
                "primary": {"headline": "No action"},
                "recommendation_count": 0,
            }

        with (
            patch(f"{service}.build_dashboard_data",
                  return_value=dashboard) as dashboard_mock,
            patch(f"{service}.build_ranked_opportunities",
                  side_effect=fake_ranked) as ranked_mock,
            patch(f"{service}.build_portfolio_health",
                  return_value=portfolio) as portfolio_mock,
            patch(f"{service}.build_ai_coach_data",
                  side_effect=fake_coach),
            patch(f"{service}.get_active_strategy",
                  return_value=object()),
            patch(f"{service}.strategy_summary",
                  return_value=strategy),
            patch(f"{service}.build_model_health",
                  side_effect=RuntimeError("Unavailable")),
        ):
            result = build_mission_control_data(object())

        self.assertEqual(len(result["ranked_opportunities"]), 5)
        self.assertEqual(len(coach_calls), 1)
        self.assertIs(coach_calls[0]["dashboard"], dashboard)
        self.assertIs(coach_calls[0]["portfolio"], portfolio)
        self.assertIs(coach_calls[0]["active_strategy"], strategy)
        self.assertEqual(len(coach_calls[0]["opportunities"]), 20)
        dashboard_mock.assert_called_once()
        portfolio_mock.assert_called_once()

        dashboard_cache = dashboard_mock.call_args.kwargs[
            "prediction_contexts"
        ]
        ranking_cache = ranked_mock.call_args.kwargs[
            "prediction_contexts"
        ]
        self.assertIs(dashboard_cache, ranking_cache)
        self.assertIsInstance(dashboard_cache, dict)
        self.assertEqual(
            [call.kwargs["limit"] for call in ranked_mock.call_args_list],
            [20],
        )


    def test_prediction_cache_is_new_for_each_request(self):
        from unittest.mock import patch

        service = "app.services.mission_control_service"
        caches = []

        def fake_dashboard(db, *, prediction_contexts):
            caches.append(prediction_contexts)
            return {
                "winner_accuracy": 70,
                "database_health": 90,
                "results_awaiting": [],
                "open_paper_trades": 0,
            }

        def fake_ranked(db, *, limit, prediction_contexts):
            self.assertIs(prediction_contexts, caches[-1])
            return []

        with (
            patch(f"{service}.build_dashboard_data",
                  side_effect=fake_dashboard),
            patch(f"{service}.build_ranked_opportunities",
                  side_effect=fake_ranked),
            patch(f"{service}.build_portfolio_health",
                  return_value={
                      "health_score": 85,
                      "open_exposure": 0,
                      "exposure_percent": 0,
                  }),
            patch(f"{service}.build_ai_coach_data",
                  return_value={
                      "primary": {"headline": "No action"},
                      "recommendation_count": 0,
                  }),
            patch(f"{service}.get_active_strategy"),
            patch(f"{service}.strategy_summary",
                  return_value={
                      "enforcement_mode": "shadow",
                      "decision_rules_enabled": False,
                  }),
            patch(f"{service}.build_model_health",
                  side_effect=RuntimeError("Unavailable")),
        ):
            build_mission_control_data(object())
            build_mission_control_data(object())

        self.assertEqual(len(caches), 2)
        self.assertIsNot(caches[0], caches[1])
        self.assertEqual(caches, [{}, {}])


if __name__ == "__main__":
    unittest.main()
