import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_history_depth_service import (
    CurrentMatchEnrichmentV33HistoryDepthService,
)


class FakeQuery:
    def __init__(self, matches):
        self.matches = matches
        self.match_id = None

    def filter(self, expression):
        self.match_id = getattr(
            getattr(expression, "right", None),
            "value",
            None,
        )
        return self

    def first(self):
        return self.matches.get(
            self.match_id
        )


class FakeDb:
    def __init__(self, matches):
        self.matches = matches

    def query(self, *args):
        return FakeQuery(
            self.matches
        )


class FakeSnapshotEngine:
    def __init__(self):
        self.calls = []

    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code,
    ):
        self.calls.append(
            (
                match_id,
                competition_code,
            )
        )

        history = {
            101: (3, 12),
            102: (8, 9),
            103: (25, 50),
        }

        history_a, history_b = history[
            match_id
        ]

        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                advanced_features=(
                    SimpleNamespace(
                        matches_available=(
                            history_a
                        )
                    )
                )
            ),
            player_b=SimpleNamespace(
                advanced_features=(
                    SimpleNamespace(
                        matches_available=(
                            history_b
                        )
                    )
                )
            ),
        )


class FakePredictionEngine:
    MODEL_VERSION = "transparent-v3.3"

    def predict(self, snapshot):
        values = {
            101: (
                "Player A",
                60.0,
            ),
            102: (
                "Player D",
                45.0,
            ),
            103: (
                "Player E",
                70.0,
            ),
        }

        predicted_winner, probability_a = (
            values[snapshot.match_id]
        )

        return SimpleNamespace(
            predicted_winner=(
                predicted_winner
            ),
            player_a_probability=(
                probability_a
            ),
        )


class CurrentMatchEnrichmentV33HistoryDepthIntegrationTests(
    unittest.TestCase
):
    @patch(
        "app.services.current_match_enrichment_v33_history_depth_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103],
    )
    def test_uses_pre_match_snapshot_history_depth(
        self,
        selector,
    ):
        matches = {
            101: SimpleNamespace(
                id=101,
                player_a="Player A",
                player_b="Player B",
                winner="Player A",
            ),
            102: SimpleNamespace(
                id=102,
                player_a="Player C",
                player_b="Player D",
                winner="Player D",
            ),
            103: SimpleNamespace(
                id=103,
                player_a="Player E",
                player_b="Player F",
                winner="Player F",
            ),
        }

        snapshot_engine = (
            FakeSnapshotEngine()
        )

        service = (
            CurrentMatchEnrichmentV33HistoryDepthService(
                snapshot_engine=(
                    snapshot_engine
                ),
                prediction_engine=(
                    FakePredictionEngine()
                ),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offset=500,
            limit=100,
            competition_code="MODUS",
        )

        selector.assert_called_once()

        self.assertEqual(
            snapshot_engine.calls,
            [
                (101, "MODUS"),
                (102, "MODUS"),
                (103, "MODUS"),
            ],
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            3,
        )

        minimum = {
            item.segment: item
            for item
            in report.minimum_history_segments
        }

        self.assertEqual(
            minimum["0-4"].predictions,
            1,
        )

        self.assertEqual(
            minimum["5-9"].predictions,
            1,
        )

        self.assertEqual(
            minimum["20-39"].predictions,
            1,
        )

        combined = {
            item.segment: item
            for item
            in report.combined_history_segments
        }

        # Matches 101 and 102 both fall in 10-19:
        # 3 + 12 = 15
        # 8 + 9 = 17
        self.assertEqual(
            combined["10-19"].predictions,
            2,
        )

        # Match 103:
        # 25 + 50 = 75
        self.assertEqual(
            combined["40-79"].predictions,
            1,
        )

    @patch(
        "app.services.current_match_enrichment_v33_history_depth_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101],
    )
    def test_correctness_and_probability_metrics_are_preserved(
        self,
        selector,
    ):
        matches = {
            101: SimpleNamespace(
                id=101,
                player_a="Player A",
                player_b="Player B",
                winner="Player A",
            ),
        }

        service = (
            CurrentMatchEnrichmentV33HistoryDepthService(
                snapshot_engine=(
                    FakeSnapshotEngine()
                ),
                prediction_engine=(
                    FakePredictionEngine()
                ),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offset=0,
            limit=1,
        )

        segment = next(
            item
            for item
            in report.minimum_history_segments
            if item.segment == "0-4"
        )

        self.assertEqual(
            segment.predictions,
            1,
        )

        self.assertEqual(
            segment.correct,
            1,
        )

        self.assertEqual(
            segment.accuracy,
            100.0,
        )

        # Player A was assigned 60%.
        self.assertEqual(
            segment.average_brier_score,
            0.16,
        )

        self.assertAlmostEqual(
            segment.average_log_loss,
            0.510826,
            places=6,
        )


if __name__ == "__main__":
    unittest.main()
