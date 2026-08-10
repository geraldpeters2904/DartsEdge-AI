import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_reliability_map_service import (
    CurrentMatchEnrichmentV33ReliabilityMapService,
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
        history = {
            101: (3, 5),
            102: (4, 7),
            103: (12, 18),
            104: (15, 22),
            105: (25, 30),
            106: (28, 35),
        }

        history_a, history_b = history[
            match_id
        ]

        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                advanced_features=SimpleNamespace(
                    matches_available=history_a
                )
            ),
            player_b=SimpleNamespace(
                advanced_features=SimpleNamespace(
                    matches_available=history_b
                )
            ),
        )


class FakePredictionEngine:
    MODEL_VERSION = "transparent-v3.3"

    def predict(self, snapshot):
        values = {
            101: ("A", 52.0, 48.0),
            102: ("C", 53.0, 47.0),
            103: ("E", 67.0, 33.0),
            104: ("G", 68.0, 32.0),
            105: ("I", 74.0, 26.0),
            106: ("K", 75.0, 25.0),
        }

        winner, probability_a, probability_b = (
            values[snapshot.match_id]
        )

        return SimpleNamespace(
            predicted_winner=winner,
            player_a_probability=probability_a,
            player_b_probability=probability_b,
        )


class CurrentMatchEnrichmentV33ReliabilityMapIntegrationTests(
    unittest.TestCase
):
    @patch(
        "app.services.current_match_enrichment_v33_reliability_map_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103, 104, 105, 106],
    )
    def test_builds_full_joint_map_and_ranks_sufficient_cells(
        self,
        selector,
    ):
        matches = {
            101: SimpleNamespace(
                id=101,
                player_a="A",
                player_b="B",
                winner="A",
            ),
            102: SimpleNamespace(
                id=102,
                player_a="C",
                player_b="D",
                winner="D",
            ),
            103: SimpleNamespace(
                id=103,
                player_a="E",
                player_b="F",
                winner="E",
            ),
            104: SimpleNamespace(
                id=104,
                player_a="G",
                player_b="H",
                winner="H",
            ),
            105: SimpleNamespace(
                id=105,
                player_a="I",
                player_b="J",
                winner="I",
            ),
            106: SimpleNamespace(
                id=106,
                player_a="K",
                player_b="L",
                winner="K",
            ),
        }

        service = (
            CurrentMatchEnrichmentV33ReliabilityMapService(
                snapshot_engine=FakeSnapshotEngine(),
                prediction_engine=FakePredictionEngine(),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offset=500,
            limit=100,
            minimum_sample=2,
            ranking_count=3,
            competition_code="MODUS",
        )

        selector.assert_called_once()

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            6,
        )

        # 6 probability bands × 5 history bands.
        self.assertEqual(
            len(report.cells),
            30,
        )

        cells = {
            (
                cell.probability_band,
                cell.history_band,
            ): cell
            for cell in report.cells
        }

        low = cells[
            ("50-55", "0-4")
        ]

        self.assertEqual(
            low.predictions,
            2,
        )

        self.assertTrue(
            low.evidence_sufficient,
        )

        mid = cells[
            ("65-70", "10-19")
        ]

        self.assertEqual(
            mid.predictions,
            2,
        )

        self.assertTrue(
            mid.evidence_sufficient,
        )

        strong = cells[
            ("70-80", "20-39")
        ]

        self.assertEqual(
            strong.predictions,
            2,
        )

        self.assertTrue(
            strong.evidence_sufficient,
        )

        self.assertTrue(
            report.strongest_cells,
        )

        self.assertTrue(
            report.weakest_cells,
        )

        self.assertLessEqual(
            len(report.strongest_cells),
            3,
        )

        self.assertLessEqual(
            len(report.weakest_cells),
            3,
        )

    @patch(
        "app.services.current_match_enrichment_v33_reliability_map_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102],
    )
    def test_insufficient_cells_are_excluded_from_rankings(
        self,
        selector,
    ):
        matches = {
            101: SimpleNamespace(
                id=101,
                player_a="A",
                player_b="B",
                winner="A",
            ),
            102: SimpleNamespace(
                id=102,
                player_a="C",
                player_b="D",
                winner="D",
            ),
        }

        service = (
            CurrentMatchEnrichmentV33ReliabilityMapService(
                snapshot_engine=FakeSnapshotEngine(),
                prediction_engine=FakePredictionEngine(),
            )
        )

        report = service.analyse(
            FakeDb(matches),
            offset=0,
            limit=10,
            minimum_sample=3,
            ranking_count=5,
        )

        self.assertEqual(
            report.matches_evaluated,
            2,
        )

        self.assertEqual(
            report.strongest_cells,
            (),
        )

        self.assertEqual(
            report.weakest_cells,
            (),
        )


if __name__ == "__main__":
    unittest.main()
