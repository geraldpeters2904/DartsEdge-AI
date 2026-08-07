import unittest
from types import SimpleNamespace

from app.services.model_health_service import (
    build_model_health,
    model_health_summary,
)


def performance_builder(db):
    return {
        "settled_count": 100,
        "sample_ready": True,
        "minimum_sample": 25,
        "leaderboard": [
            {
                "name": "Player Intelligence",
                "settled": 100,
                "accuracy": 0.59,
                "brier": 0.245,
                "calibration_error": 0.055,
            },
        ],
        "recent_metrics": {
            "accuracy": 0.64,
        },
        "prior_metrics": {
            "accuracy": 0.56,
        },
        "accuracy_drift": 0.08,
    }


def trust_builder(
    db,
    *,
    model_name,
    offset,
    limit,
):
    return SimpleNamespace(
        model_name=model_name,
        model_version=(
            "transparent-v3.3"
        ),
        trust_score=74,
        trust_grade="High",
    )


def strategy_builder(db):
    return {
        "metrics": [
            SimpleNamespace(
                roi_percent=12.5,
                profit_loss=125.0,
                maximum_drawdown=20.0,
            ),
        ],
    }


def portfolio_builder(db):
    return {
        "roi": 8.0,
        "total_profit_loss": 80.0,
    }


class ModelHealthServiceTests(
    unittest.TestCase
):
    def build(self):
        return build_model_health(
            object(),
            performance_builder=(
                performance_builder
            ),
            trust_builder=(
                trust_builder
            ),
            strategy_builder=(
                strategy_builder
            ),
            portfolio_builder=(
                portfolio_builder
            ),
        )

    def test_builds_health_report(self):
        report = self.build()

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            report.settled_predictions,
            100,
        )
        self.assertTrue(
            report.sample_ready
        )
        self.assertGreaterEqual(
            report.health_score,
            70,
        )

    def test_normalises_fractional_metrics(self):
        report = self.build()

        self.assertEqual(
            report.accuracy_percent,
            59.0,
        )
        self.assertEqual(
            report.recent_accuracy_percent,
            64.0,
        )
        self.assertEqual(
            report.accuracy_drift_points,
            8.0,
        )

    def test_includes_trading_metrics(self):
        report = self.build()

        self.assertEqual(
            report.strategy_roi_percent,
            12.5,
        )
        self.assertEqual(
            report.strategy_profit_loss,
            125.0,
        )
        self.assertEqual(
            report.maximum_drawdown,
            20.0,
        )

    def test_summary_is_json_ready(self):
        payload = model_health_summary(
            self.build()
        )

        self.assertIsInstance(
            payload["components"],
            dict,
        )
        self.assertIsInstance(
            payload[
                "positive_findings"
            ],
            list,
        )
        self.assertIsInstance(
            payload["warnings"],
            list,
        )

    def test_small_sample_caps_health(self):
        def small_performance(db):
            data = performance_builder(
                db
            )
            data[
                "settled_count"
            ] = 10
            data[
                "sample_ready"
            ] = False
            return data

        report = build_model_health(
            object(),
            performance_builder=(
                small_performance
            ),
            trust_builder=(
                trust_builder
            ),
            strategy_builder=(
                strategy_builder
            ),
            portfolio_builder=(
                portfolio_builder
            ),
        )

        self.assertLessEqual(
            report.health_score,
            64,
        )
        self.assertIn(
            "settled prediction sample",
            " ".join(
                report.warnings
            ).lower(),
        )


if __name__ == "__main__":
    unittest.main()
