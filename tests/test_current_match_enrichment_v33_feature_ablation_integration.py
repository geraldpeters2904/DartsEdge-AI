import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_feature_ablation_service import (
    CurrentMatchEnrichmentV33FeatureAblationService,
)


class FakeAblationService(
    CurrentMatchEnrichmentV33FeatureAblationService
):
    def __init__(self):
        self.calls = []

    def _validate(
        self,
        db,
        *,
        engine,
        offset,
        limit,
        competition_code,
    ):
        names = tuple(
            feature.name
            for feature in engine.features
        )

        self.calls.append(
            {
                "model_version": engine.MODEL_VERSION,
                "feature_names": names,
                "offset": offset,
                "limit": limit,
                "competition_code": competition_code,
            }
        )

        # Baseline contains scoring_power.
        if "scoring_power" in names:
            return SimpleNamespace(
                model_version="transparent-v3.3",
                matches_evaluated=100,
                accuracy=62.0,
                average_brier_score=0.220,
                average_log_loss=0.640,
            )

        # Removing scoring_power makes the model worse.
        return SimpleNamespace(
            model_version="transparent-v3.3",
            matches_evaluated=100,
            accuracy=58.0,
            average_brier_score=0.240,
            average_log_loss=0.680,
        )


class CurrentMatchEnrichmentV33FeatureAblationIntegrationTests(
    unittest.TestCase
):
    def test_analyse_uses_v33_and_same_historical_window(self):
        service = FakeAblationService()

        report = service.analyse(
            object(),
            offset=250,
            limit=100,
            competition_code="MODUS",
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            100,
        )

        self.assertGreater(
            len(service.calls),
            1,
        )

        for call in service.calls:
            self.assertEqual(
                call["model_version"],
                "transparent-v3.3",
            )
            self.assertEqual(
                call["offset"],
                250,
            )
            self.assertEqual(
                call["limit"],
                100,
            )
            self.assertEqual(
                call["competition_code"],
                "MODUS",
            )

    def test_zero_weight_v33_features_are_not_ablated(self):
        service = FakeAblationService()

        report = service.analyse(
            object(),
            offset=0,
            limit=100,
        )

        names = {
            item.feature_name
            for item in report.features
        }

        self.assertNotIn(
            "overall_strength",
            names,
        )

        self.assertNotIn(
            "recent_form",
            names,
        )

    def test_helpful_feature_receives_positive_importance(self):
        service = FakeAblationService()

        report = service.analyse(
            object(),
            offset=0,
            limit=100,
        )

        scoring = next(
            item
            for item in report.features
            if item.feature_name
            == "scoring_power"
        )

        self.assertGreater(
            scoring.accuracy_drop,
            0.0,
        )

        self.assertGreater(
            scoring.brier_increase,
            0.0,
        )

        self.assertGreater(
            scoring.log_loss_increase,
            0.0,
        )

        self.assertGreater(
            scoring.importance_score,
            0.0,
        )

        self.assertTrue(
            scoring.helpful,
        )

    def test_report_is_sorted_by_importance(self):
        service = FakeAblationService()

        report = service.analyse(
            object(),
            offset=0,
            limit=100,
        )

        importance = [
            item.importance_score
            for item in report.features
        ]

        self.assertEqual(
            importance,
            sorted(
                importance,
                reverse=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
