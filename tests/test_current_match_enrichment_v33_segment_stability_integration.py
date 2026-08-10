import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_segment_stability_service import (
    CurrentMatchEnrichmentV33SegmentStabilityService,
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
    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code,
    ):
        values = {
            101: (25, 30),
            102: (12, 18),
            103: (22, 35),
            104: (25, 28),
        }

        history_a, history_b = values[
            match_id
        ]

        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                advanced_features=(
                    SimpleNamespace(
                        matches_available=history_a
                    )
                )
            ),
            player_b=SimpleNamespace(
                advanced_features=(
                    SimpleNamespace(
                        matches_available=history_b
                    )
                )
            ),
        )


class FakePredictionEngine:
    MODEL_VERSION = "transparent-v3.3"

    def predict(self, snapshot):
        values = {
            # 67% favourite, history 25 -> selected
            101: (
                "Player A",
                67.0,
                33.0,
            ),

            # 68% favourite, history 12 -> control,
            # not selected for 20-39
            102: (
                "Player C",
                68.0,
                32.0,
            ),

            # 72% favourite, history 22 -> probability
            # outside requested 65-70 band
            103: (
                "Player E",
                72.0,
                28.0,
            ),

            # 66% favourite, history 25 -> selected
            104: (
                "Player G",
                66.0,
                34.0,
            ),
        }

        winner, probability_a, probability_b = (
            values[snapshot.match_id]
        )

        return SimpleNamespace(
            predicted_winner=winner,
            player_a_probability=probability_a,
            player_b_probability=probability_b,
        )


class CurrentMatchEnrichmentV33SegmentStabilityIntegrationTests(
    unittest.TestCase
):
    @patch(
        "app.services.current_match_enrichment_v33_segment_stability_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103, 104],
    )
    def test_joint_probability_and_history_segment(
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
                winner="Player E",
            ),
            104: SimpleNamespace(
                id=104,
                player_a="Player G",
                player_b="Player H",
                winner="Player H",
            ),
        }

        service = (
            CurrentMatchEnrichmentV33SegmentStabilityService(
                snapshot_engine=FakeSnapshotEngine(),
                prediction_engine=FakePredictionEngine(),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offsets=(500,),
            window_size=100,
            probability_lower=65.0,
            probability_upper=70.0,
            history_lower=20,
            history_upper=40,
            competition_code="MODUS",
        )

        selector.assert_called_once()

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.windows_completed,
            1,
        )

        self.assertEqual(
            report.total_matches_evaluated,
            4,
        )

        # Only 101 and 104 meet BOTH conditions.
        self.assertEqual(
            report.total_segment_matches,
            2,
        )

        window = report.windows[0]

        self.assertEqual(
            window.segment_matches,
            2,
        )

        # Match 101 correct, 104 incorrect.
        self.assertEqual(
            window.correct,
            1,
        )

        self.assertEqual(
            window.accuracy,
            50.0,
        )

    @patch(
        "app.services.current_match_enrichment_v33_segment_stability_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103, 104],
    )
    def test_control_history_band_selects_different_match(
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
                winner="Player E",
            ),
            104: SimpleNamespace(
                id=104,
                player_a="Player G",
                player_b="Player H",
                winner="Player H",
            ),
        }

        service = (
            CurrentMatchEnrichmentV33SegmentStabilityService(
                snapshot_engine=FakeSnapshotEngine(),
                prediction_engine=FakePredictionEngine(),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offsets=(500,),
            window_size=100,
            probability_lower=65.0,
            probability_upper=70.0,
            history_lower=10,
            history_upper=20,
        )

        self.assertEqual(
            report.total_segment_matches,
            1,
        )

        window = report.windows[0]

        # Only match 102 belongs in the control.
        self.assertEqual(
            window.segment_matches,
            1,
        )

        self.assertEqual(
            window.correct,
            0,
        )

        self.assertEqual(
            window.accuracy,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
