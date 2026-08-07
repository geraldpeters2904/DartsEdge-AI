import unittest
from types import SimpleNamespace

from app.services.model_benchmark_laboratory import (
    ModelBenchmarkLaboratory,
)


class ModelBenchmarkLaboratoryTests(
    unittest.TestCase
):
    def test_summarises_multiple_windows(self):
        windows = (
            SimpleNamespace(
                accuracy_winner="a",
                brier_winner="b",
                log_loss_winner="b",
                summaries=(
                    SimpleNamespace(
                        model_name="a",
                        model_version="a-v1",
                        matches_evaluated=100,
                        accuracy=60.0,
                        average_brier_score=0.25,
                        average_log_loss=0.70,
                    ),
                    SimpleNamespace(
                        model_name="b",
                        model_version="b-v1",
                        matches_evaluated=100,
                        accuracy=59.0,
                        average_brier_score=0.23,
                        average_log_loss=0.66,
                    ),
                ),
            ),
            SimpleNamespace(
                accuracy_winner="b",
                brier_winner="b",
                log_loss_winner="b",
                summaries=(
                    SimpleNamespace(
                        model_name="a",
                        model_version="a-v1",
                        matches_evaluated=100,
                        accuracy=58.0,
                        average_brier_score=0.27,
                        average_log_loss=0.75,
                    ),
                    SimpleNamespace(
                        model_name="b",
                        model_version="b-v1",
                        matches_evaluated=100,
                        accuracy=61.0,
                        average_brier_score=0.22,
                        average_log_loss=0.64,
                    ),
                ),
            ),
        )

        summary = (
            ModelBenchmarkLaboratory
            ._summarise_model(
                "b",
                windows,
            )
        )

        self.assertEqual(
            summary.average_accuracy,
            60.0,
        )
        self.assertEqual(
            summary.accuracy_window_wins,
            1,
        )
        self.assertEqual(
            summary.brier_window_wins,
            2,
        )
        self.assertEqual(
            summary.log_loss_window_wins,
            2,
        )
        self.assertEqual(
            summary.matches_evaluated,
            200,
        )


if __name__ == "__main__":
    unittest.main()
