import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_segmentation_service import (
    CurrentMatchEnrichmentV33SegmentationService,
)


class FakeValidationEngine:
    last_match_ids = None
    last_competition_code = None
    last_include_records = None

    def __init__(
        self,
        *,
        prediction_engine,
        **kwargs,
    ):
        self.prediction_engine = prediction_engine

    def validate_matches(
        self,
        db,
        *,
        match_ids,
        competition_code,
        include_records,
    ):
        FakeValidationEngine.last_match_ids = tuple(
            match_ids
        )
        FakeValidationEngine.last_competition_code = (
            competition_code
        )
        FakeValidationEngine.last_include_records = (
            include_records
        )

        records = (
            SimpleNamespace(
                favourite_probability=52.0,
                confidence=45.0,
                correct=True,
                brier_score=0.20,
                log_loss=0.60,
                tournament="MODUS Super Series",
                stage="Group A",
            ),
            SimpleNamespace(
                favourite_probability=58.0,
                confidence=55.0,
                correct=False,
                brier_score=0.30,
                log_loss=0.80,
                tournament="MODUS Super Series",
                stage="Group A",
            ),
            SimpleNamespace(
                favourite_probability=67.0,
                confidence=72.0,
                correct=True,
                brier_score=0.15,
                log_loss=0.50,
                tournament="MODUS Super Series",
                stage="Final",
            ),
        )

        return SimpleNamespace(
            model_version="transparent-v3.3",
            matches_evaluated=3,
            accuracy=66.667,
            average_brier_score=0.216667,
            average_log_loss=0.633333,
            records=records,
        )


class CurrentMatchEnrichmentV33SegmentationIntegrationTests(
    unittest.TestCase
):
    @patch(
        "app.services.current_match_enrichment_v33_segmentation_service."
        "PredictionValidationEngine",
        FakeValidationEngine,
    )
    @patch(
        "app.services.current_match_enrichment_v33_segmentation_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103],
    )
    def test_uses_validation_records_and_same_match_sample(
        self,
        selector,
    ):
        service = (
            CurrentMatchEnrichmentV33SegmentationService()
        )

        report = service.analyse(
            object(),
            offset=500,
            limit=100,
            competition_code="MODUS",
        )

        selector.assert_called_once()

        self.assertEqual(
            FakeValidationEngine.last_match_ids,
            (101, 102, 103),
        )

        self.assertEqual(
            FakeValidationEngine.last_competition_code,
            "MODUS",
        )

        self.assertTrue(
            FakeValidationEngine.last_include_records
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            3,
        )

        self.assertEqual(
            report.overall_accuracy,
            66.667,
        )

        probability = {
            item.segment: item
            for item in report.probability_segments
        }

        self.assertEqual(
            probability["50-55"].predictions,
            1,
        )

        self.assertEqual(
            probability["55-60"].predictions,
            1,
        )

        self.assertEqual(
            probability["65-70"].predictions,
            1,
        )

    @patch(
        "app.services.current_match_enrichment_v33_segmentation_service."
        "PredictionValidationEngine",
        FakeValidationEngine,
    )
    @patch(
        "app.services.current_match_enrichment_v33_segmentation_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103],
    )
    def test_stage_and_confidence_segments_are_reported(
        self,
        selector,
    ):
        service = (
            CurrentMatchEnrichmentV33SegmentationService()
        )

        report = service.analyse(
            object(),
            offset=0,
            limit=100,
        )

        confidence = {
            item.segment: item
            for item in report.confidence_segments
        }

        self.assertEqual(
            confidence["40-60"].predictions,
            2,
        )

        self.assertEqual(
            confidence["60-80"].predictions,
            1,
        )

        stages = {
            item.segment: item
            for item in report.stage_segments
        }

        self.assertEqual(
            stages["Group A"].predictions,
            2,
        )

        self.assertEqual(
            stages["Final"].predictions,
            1,
        )


if __name__ == "__main__":
    unittest.main()
