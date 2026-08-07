import unittest
from types import SimpleNamespace

from app.services.model_trust_service import (
    build_model_trust_report,
    trust_summary,
)


class FakeQuery:
    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def offset(self, value):
        return self

    def limit(self, value):
        return self

    def all(self):
        return [
            (match_id,)
            for match_id in range(
                1,
                1001,
            )
        ]


class FakeDb:
    def query(self, *args):
        return FakeQuery()


class FakeRegistry:
    def get_registered(self, name):
        return SimpleNamespace(
            name=name,
            version="transparent-v3.3",
        )


class FakePerformanceLab:
    def evaluate_model(
        self,
        db,
        *,
        model_name,
        match_ids,
        competition_code=None,
    ):
        return SimpleNamespace(
            model_name=model_name,
            model_version="transparent-v3.3",
            matches_considered=1000,
            matches_evaluated=1000,
            matches_skipped=0,
            correct_predictions=590,
            accuracy=59.0,
            average_brier_score=0.245,
            average_log_loss=0.685,
            best_confidence_band="80+",
            best_confidence_accuracy=65.0,
            weakest_confidence_band="0-40",
            weakest_confidence_accuracy=50.0,
            best_tournament="MODUS",
            best_tournament_accuracy=60.0,
            weakest_tournament="Other",
            weakest_tournament_accuracy=53.0,
            best_stage="Group C",
            best_stage_accuracy=62.0,
            weakest_stage="Final",
            weakest_stage_accuracy=50.0,
        )


def metric(
    label,
    predictions,
    accuracy,
):
    return SimpleNamespace(
        segment_type="test",
        segment_label=label,
        predictions=predictions,
        correct=int(
            predictions
            * accuracy
            / 100.0
        ),
        accuracy=accuracy,
        average_brier_score=0.25,
        average_log_loss=0.70,
    )


class FakeSegmentLab:
    def compare(
        self,
        db,
        *,
        model_names,
        offset,
        limit,
        competition_code=None,
    ):
        summary = SimpleNamespace(
            model_name="transparent-v3.3",
            model_version="transparent-v3.3",
            matches_evaluated=1000,
            favourite_bands=(),
            confidence_bands=(
                metric(
                    "40-60",
                    100,
                    54.0,
                ),
                metric(
                    "60-80",
                    600,
                    58.0,
                ),
                metric(
                    "80+",
                    300,
                    64.0,
                ),
            ),
            stages=(
                metric(
                    "Group A",
                    400,
                    57.0,
                ),
                metric(
                    "Group B",
                    250,
                    59.0,
                ),
                metric(
                    "Group C",
                    300,
                    62.0,
                ),
                metric(
                    "Final",
                    50,
                    50.0,
                ),
            ),
        )

        return SimpleNamespace(
            model_summaries=(
                summary,
            ),
        )


class ModelTrustServiceTests(
    unittest.TestCase
):
    def build(self):
        return build_model_trust_report(
            FakeDb(),
            model_name="transparent-v3.3",
            limit=1000,
            model_registry=FakeRegistry(),
            performance_laboratory=(
                FakePerformanceLab()
            ),
            segment_laboratory=(
                FakeSegmentLab()
            ),
        )

    def test_builds_trust_report(self):
        report = self.build()

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            report.sample_size,
            1000,
        )
        self.assertGreaterEqual(
            report.trust_score,
            60,
        )
        self.assertLessEqual(
            report.trust_score,
            100,
        )

    def test_identifies_strongest_segments(self):
        report = self.build()

        self.assertEqual(
            report.strongest_confidence_band,
            "80+",
        )
        self.assertEqual(
            report.weakest_confidence_band,
            "40-60",
        )
        self.assertEqual(
            report.strongest_stage,
            "Group C",
        )
        self.assertEqual(
            report.weakest_stage,
            "Final",
        )

    def test_produces_reason_collections(self):
        report = self.build()

        self.assertTrue(
            report.positive_reasons
        )
        self.assertIsInstance(
            report.caution_reasons,
            tuple,
        )

    def test_summary_is_json_ready(self):
        payload = trust_summary(
            self.build()
        )

        self.assertIsInstance(
            payload[
                "positive_reasons"
            ],
            list,
        )
        self.assertIsInstance(
            payload[
                "caution_reasons"
            ],
            list,
        )
        self.assertIn(
            "trust_score",
            payload,
        )


if __name__ == "__main__":
    unittest.main()
