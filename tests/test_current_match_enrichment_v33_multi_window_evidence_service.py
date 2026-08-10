import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_multi_window_evidence_service import (
    CurrentMatchEnrichmentV33MultiWindowEvidenceService,
)


def feature(
    name,
    *,
    weight,
    importance,
    accuracy_drop,
    brier_increase,
    log_loss_increase,
):
    return SimpleNamespace(
        feature_name=name,
        feature_weight=weight,
        importance_score=importance,
        accuracy_drop=accuracy_drop,
        brier_increase=brier_increase,
        log_loss_increase=log_loss_increase,
        helpful=importance > 0,
        harmful=importance < 0,
    )


class FakeAblationService:
    def __init__(self):
        self.calls = []

    def analyse(
        self,
        db,
        *,
        offset,
        limit,
        competition_code,
    ):
        self.calls.append(
            (
                offset,
                limit,
                competition_code,
            )
        )

        if offset == 100:
            features = (
                feature(
                    "scoring_power",
                    weight=0.15,
                    importance=0.06,
                    accuracy_drop=8.0,
                    brier_increase=0.02,
                    log_loss_increase=0.04,
                ),
                feature(
                    "finishing_strength",
                    weight=0.12,
                    importance=-0.03,
                    accuracy_drop=-4.0,
                    brier_increase=-0.01,
                    log_loss_increase=-0.02,
                ),
            )
        else:
            features = (
                feature(
                    "scoring_power",
                    weight=0.15,
                    importance=0.04,
                    accuracy_drop=4.0,
                    brier_increase=0.01,
                    log_loss_increase=0.03,
                ),
                feature(
                    "finishing_strength",
                    weight=0.12,
                    importance=0.01,
                    accuracy_drop=0.0,
                    brier_increase=0.01,
                    log_loss_increase=0.02,
                ),
            )

        return SimpleNamespace(
            model_version="transparent-v3.3",
            offset=offset,
            limit=limit,
            matches_evaluated=limit,
            baseline_accuracy=60.0,
            baseline_brier_score=0.23,
            baseline_log_loss=0.66,
            features=features,
        )


class CurrentMatchEnrichmentV33MultiWindowEvidenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.ablation = FakeAblationService()
        self.service = (
            CurrentMatchEnrichmentV33MultiWindowEvidenceService(
                ablation_service=self.ablation,
            )
        )

    def test_analyses_each_requested_window(self):
        report = self.service.analyse(
            object(),
            offsets=(100, 200),
            window_size=100,
            competition_code="MODUS",
        )

        self.assertEqual(
            self.ablation.calls,
            [
                (100, 100, "MODUS"),
                (200, 100, "MODUS"),
            ],
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            report.windows_completed,
            2,
        )
        self.assertEqual(
            report.total_matches_evaluated,
            200,
        )

    def test_aggregates_feature_consensus(self):
        report = self.service.analyse(
            object(),
            offsets=(100, 200),
            window_size=100,
        )

        scoring = next(
            item
            for item in report.features
            if item.feature_name
            == "scoring_power"
        )

        self.assertEqual(
            scoring.helpful_windows,
            2,
        )
        self.assertEqual(
            scoring.harmful_windows,
            0,
        )
        self.assertEqual(
            scoring.helpful_percentage,
            100.0,
        )
        self.assertEqual(
            scoring.average_importance,
            0.05,
        )

        finishing = next(
            item
            for item in report.features
            if item.feature_name
            == "finishing_strength"
        )

        self.assertEqual(
            finishing.helpful_windows,
            1,
        )
        self.assertEqual(
            finishing.harmful_windows,
            1,
        )
        self.assertEqual(
            finishing.helpful_percentage,
            50.0,
        )

    def test_features_are_ranked_by_average_importance(self):
        report = self.service.analyse(
            object(),
            offsets=(100, 200),
        )

        self.assertEqual(
            report.features[0].feature_name,
            "scoring_power",
        )

    def test_requires_at_least_one_offset(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                offsets=(),
            )

    def test_rejects_negative_offset(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            self.service.analyse(
                object(),
                offsets=(-1,),
            )

    def test_rejects_non_positive_window(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                window_size=0,
            )

    def test_average_ignores_missing_values(self):
        self.assertEqual(
            self.service._average(
                [
                    1.0,
                    None,
                    3.0,
                ]
            ),
            2.0,
        )

        self.assertIsNone(
            self.service._average(
                [
                    None,
                    None,
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
