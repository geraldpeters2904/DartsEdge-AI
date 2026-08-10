import unittest

from app.services.current_match_enrichment_v33_reliability_map_service import (
    CurrentMatchEnrichmentV33ReliabilityMapService,
    _ReliabilityRecord,
)


class CurrentMatchEnrichmentV33ReliabilityMapServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33ReliabilityMapService()
        )

    def test_build_cell_selects_joint_segment(self):
        records = (
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=67.0,
                minimum_history=25,
            ),
            _ReliabilityRecord(
                correct=False,
                brier_score=0.45,
                log_loss=1.05,
                favourite_probability=68.0,
                minimum_history=30,
            ),
            _ReliabilityRecord(
                correct=True,
                brier_score=0.12,
                log_loss=0.42,
                favourite_probability=62.0,
                minimum_history=25,
            ),
            _ReliabilityRecord(
                correct=True,
                brier_score=0.11,
                log_loss=0.41,
                favourite_probability=67.0,
                minimum_history=12,
            ),
        )

        cell = self.service._build_cell(
            records,
            probability_lower=65,
            probability_upper=70,
            history_lower=20,
            history_upper=40,
            minimum_sample=2,
        )

        self.assertEqual(
            cell.probability_band,
            "65-70",
        )
        self.assertEqual(
            cell.history_band,
            "20-39",
        )
        self.assertEqual(
            cell.predictions,
            2,
        )
        self.assertEqual(
            cell.correct,
            1,
        )
        self.assertEqual(
            cell.accuracy,
            50.0,
        )
        self.assertTrue(
            cell.evidence_sufficient
        )
        self.assertIsNotNone(
            cell.reliability_score
        )

    def test_insufficient_cell_is_not_rankable(self):
        records = (
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=67.0,
                minimum_history=25,
            ),
        )

        cell = self.service._build_cell(
            records,
            probability_lower=65,
            probability_upper=70,
            history_lower=20,
            history_upper=40,
            minimum_sample=30,
        )

        self.assertEqual(
            cell.predictions,
            1,
        )
        self.assertFalse(
            cell.evidence_sufficient
        )
        self.assertIsNone(
            cell.reliability_score
        )

    def test_history_upper_is_exclusive(self):
        records = (
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=67.0,
                minimum_history=39,
            ),
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=67.0,
                minimum_history=40,
            ),
        )

        cell = self.service._build_cell(
            records,
            probability_lower=65,
            probability_upper=70,
            history_lower=20,
            history_upper=40,
            minimum_sample=1,
        )

        self.assertEqual(
            cell.predictions,
            1,
        )

    def test_probability_upper_is_exclusive(self):
        records = (
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=69.999,
                minimum_history=25,
            ),
            _ReliabilityRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                favourite_probability=70.0,
                minimum_history=25,
            ),
        )

        cell = self.service._build_cell(
            records,
            probability_lower=65,
            probability_upper=70,
            history_lower=20,
            history_upper=40,
            minimum_sample=1,
        )

        self.assertEqual(
            cell.predictions,
            1,
        )

    def test_open_history_band_label(self):
        self.assertEqual(
            self.service._history_label(
                40,
                None,
            ),
            "40+",
        )

    def test_reliability_score_rewards_better_metrics(self):
        stronger = (
            self.service._reliability_score(
                accuracy=70.0,
                brier=0.20,
                log_loss=0.60,
            )
        )

        weaker = (
            self.service._reliability_score(
                accuracy=55.0,
                brier=0.27,
                log_loss=0.75,
            )
        )

        self.assertGreater(
            stronger,
            weaker,
        )

    def test_rejects_invalid_minimum_sample(self):
        with self.assertRaisesRegex(
            ValueError,
            "minimum_sample",
        ):
            self.service.analyse(
                object(),
                minimum_sample=0,
            )

    def test_rejects_invalid_ranking_count(self):
        with self.assertRaisesRegex(
            ValueError,
            "ranking_count",
        ):
            self.service.analyse(
                object(),
                ranking_count=0,
            )


if __name__ == "__main__":
    unittest.main()
