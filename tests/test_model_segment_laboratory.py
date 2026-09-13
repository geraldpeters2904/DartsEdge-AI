import unittest

from unittest.mock import patch
from types import SimpleNamespace

from app.services.model_segment_laboratory import (
    ModelSegmentLaboratory,
)


class ModelSegmentLaboratoryTests(
    unittest.TestCase
):
    def test_v35_uses_advanced_historical_snapshot_engine(self):
        registered = SimpleNamespace(
            name="transparent",
            version="transparent-v3.5",
            model=object(),
        )
        registry = SimpleNamespace(
            get_registered=lambda model_name: registered
        )
        laboratory = ModelSegmentLaboratory(
            model_registry=registry
        )

        validation_report = SimpleNamespace(
            records=(),
            matches_evaluated=0,
        )

        with patch(
            "app.services.model_segment_laboratory."
            "AdvancedHistoricalSnapshotEngine"
        ) as advanced_engine, patch(
            "app.services.model_segment_laboratory."
            "PredictionValidationEngine"
        ) as validation_engine:
            snapshot = object()
            advanced_engine.return_value = snapshot

            validation_engine.return_value.validate_matches.return_value = (
                validation_report
            )

            laboratory._evaluate_model(
                None,
                model_name="transparent",
                match_ids=(),
                competition_code=None,
            )

        advanced_engine.assert_called_once_with()
        validation_engine.assert_called_once_with(
            snapshot_engine=snapshot,
            prediction_engine=registered.model,
        )

    def test_builds_segment_metric(self):
        records = (
            SimpleNamespace(
                correct=True,
                brier_score=0.16,
                log_loss=0.51,
                favourite_probability=65.0,
                confidence=70.0,
                stage="Group A",
            ),
            SimpleNamespace(
                correct=False,
                brier_score=0.36,
                log_loss=0.92,
                favourite_probability=68.0,
                confidence=72.0,
                stage="Group A",
            ),
        )

        metric = ModelSegmentLaboratory._metric(
            records,
            segment_type="favourite",
            segment_label="60-70",
            predicate=lambda record: (
                60
                <= record.favourite_probability
                < 70
            ),
        )

        self.assertEqual(
            metric.predictions,
            2,
        )
        self.assertEqual(
            metric.correct,
            1,
        )
        self.assertEqual(
            metric.accuracy,
            50.0,
        )
        self.assertEqual(
            metric.average_brier_score,
            0.26,
        )


if __name__ == "__main__":
    unittest.main()
