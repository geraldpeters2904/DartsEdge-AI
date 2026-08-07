import unittest
from types import SimpleNamespace

from app.services.model_performance_laboratory import (
    ModelPerformanceLaboratory,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
)


class FakeModel:
    def __init__(self, version):
        self.MODEL_VERSION = version

    def predict(self, snapshot):
        return snapshot


class FakeValidationReport:
    def __init__(
        self,
        *,
        accuracy,
        brier,
        log_loss,
    ):
        self.matches_considered = 100
        self.matches_evaluated = 90
        self.matches_skipped = 10
        self.correct_predictions = int(
            90 * accuracy / 100
        )
        self.accuracy = accuracy
        self.average_brier_score = brier
        self.average_log_loss = log_loss
        self.confidence_bands = (
            SimpleNamespace(
                lower_bound=0,
                upper_bound=40,
                predictions=10,
                accuracy=50.0,
            ),
            SimpleNamespace(
                lower_bound=80,
                upper_bound=101,
                predictions=20,
                accuracy=75.0,
            ),
        )
        self.accuracy_by_tournament = {
            "Series 1": 65.0,
            "Series 2": 72.0,
        }
        self.accuracy_by_stage = {
            "Group A": 68.0,
            "Final": 74.0,
        }


class FakeValidationEngine:
    reports = {}

    def __init__(
        self,
        *,
        snapshot_engine,
        prediction_engine,
    ):
        self.prediction_engine = (
            prediction_engine
        )

    def validate_matches(
        self,
        db,
        *,
        match_ids=None,
        competition_code=None,
        include_records=False,
    ):
        return self.reports[
            self.prediction_engine.MODEL_VERSION
        ]


class ModelPerformanceLaboratoryTests(
    unittest.TestCase
):
    def setUp(self):
        self.registry = PredictionModelRegistry(
            models=[
                (
                    "model-a",
                    FakeModel("model-a-v1"),
                ),
                (
                    "model-b",
                    FakeModel("model-b-v1"),
                ),
            ],
            default_model="model-a",
        )

    def test_summarises_validation_report(self):
        report = FakeValidationReport(
            accuracy=70.0,
            brier=0.20,
            log_loss=0.60,
        )

        summary = (
            ModelPerformanceLaboratory
            ._summarise(
                "model-a",
                "model-a-v1",
                report,
            )
        )

        self.assertEqual(
            summary.matches_evaluated,
            90,
        )
        self.assertEqual(
            summary.best_confidence_band,
            "80-101",
        )
        self.assertEqual(
            summary.best_tournament,
            "Series 2",
        )
        self.assertEqual(
            summary.weakest_stage,
            "Group A",
        )

    def test_ranking_prefers_accuracy_then_brier(self):
        high_accuracy = (
            ModelPerformanceLaboratory
            ._summarise(
                "high",
                "high-v1",
                FakeValidationReport(
                    accuracy=71.0,
                    brier=0.25,
                    log_loss=0.65,
                ),
            )
        )
        low_accuracy = (
            ModelPerformanceLaboratory
            ._summarise(
                "low",
                "low-v1",
                FakeValidationReport(
                    accuracy=70.0,
                    brier=0.18,
                    log_loss=0.55,
                ),
            )
        )

        ranked = sorted(
            (low_accuracy, high_accuracy),
            key=(
                ModelPerformanceLaboratory
                ._ranking_key
            ),
        )

        self.assertEqual(
            ranked[0].model_name,
            "high",
        )


if __name__ == "__main__":
    unittest.main()
