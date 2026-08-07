import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.automatic_settlement_pipeline_service import (
    run_automatic_settlement,
)


class AutomaticSettlementPipelineTests(
    unittest.TestCase
):
    @patch(
        "app.services.automatic_settlement_pipeline_service.settle_completed_prediction_audits"
    )
    def test_runs_refreshes_after_new_settlement(
        self,
        settle,
    ):
        settle.return_value = (
            SimpleNamespace(
                audits_scanned=10,
                settled=2,
                already_settled=6,
                missing_match=1,
                invalid_match_result=1,
            )
        )

        calls = []

        def hook(
            name,
        ):
            def callback(
                db,
            ):
                calls.append(
                    name
                )
                return (
                    f"{name} refreshed"
                )
            return callback

        report = (
            run_automatic_settlement(
                object(),
                clv_refresh=(
                    hook(
                        "clv"
                    )
                ),
                strategy_refresh=(
                    hook(
                        "strategy"
                    )
                ),
                portfolio_refresh=(
                    hook(
                        "portfolio"
                    )
                ),
                model_health_refresh=(
                    hook(
                        "health"
                    )
                ),
            )
        )

        self.assertEqual(
            report.settled,
            2,
        )

        self.assertEqual(
            calls,
            [
                "clv",
                "strategy",
                "portfolio",
                "health",
            ],
        )

        self.assertTrue(
            report.success
        )

    @patch(
        "app.services.automatic_settlement_pipeline_service.settle_completed_prediction_audits"
    )
    def test_no_refresh_when_nothing_new(
        self,
        settle,
    ):
        settle.return_value = (
            SimpleNamespace(
                audits_scanned=5,
                settled=0,
                already_settled=5,
                missing_match=0,
                invalid_match_result=0,
            )
        )

        calls = []

        report = (
            run_automatic_settlement(
                object(),
                model_health_refresh=(
                    lambda db: (
                        calls.append(
                            "health"
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            calls,
            [],
        )

        self.assertEqual(
            report.stages,
            (),
        )

        self.assertTrue(
            report.success
        )

    @patch(
        "app.services.automatic_settlement_pipeline_service.settle_completed_prediction_audits"
    )
    def test_refresh_failure_does_not_undo_settlement(
        self,
        settle,
    ):
        settle.return_value = (
            SimpleNamespace(
                audits_scanned=1,
                settled=1,
                already_settled=0,
                missing_match=0,
                invalid_match_result=0,
            )
        )

        def fail(
            db,
        ):
            raise RuntimeError(
                "analytics unavailable"
            )

        report = (
            run_automatic_settlement(
                object(),
                model_health_refresh=fail,
            )
        )

        self.assertEqual(
            report.settled,
            1,
        )

        self.assertFalse(
            report.success
        )

        failed = [
            stage
            for stage
            in report.stages
            if not stage.success
        ]

        self.assertEqual(
            len(
                failed
            ),
            1,
        )

        self.assertIn(
            "analytics unavailable",
            failed[0].error,
        )


if __name__ == "__main__":
    unittest.main()
