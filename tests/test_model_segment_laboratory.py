import unittest
from types import SimpleNamespace

from app.services.model_segment_laboratory import (
    ModelSegmentLaboratory,
)


class ModelSegmentLaboratoryTests(
    unittest.TestCase
):
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
