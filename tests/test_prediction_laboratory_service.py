import unittest
from types import SimpleNamespace

from app.services.prediction_laboratory_service import (
    PredictionLaboratoryService,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
)


class FakeModel:
    MODEL_VERSION = "fake-v1"

    def predict(self, snapshot):
        contributions = (
            SimpleNamespace(
                feature="overall",
                raw_edge=50.0,
                weighted_score=0.20,
            ),
            SimpleNamespace(
                feature="finishing",
                raw_edge=-20.0,
                weighted_score=-0.05,
            ),
        )

        return SimpleNamespace(
            predicted_winner="Player A",
            contributions=contributions,
        )


class FakeSnapshotEngine:
    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code=None,
    ):
        return SimpleNamespace(
            match_id=match_id,
            match_date="2026-08-05",
            tournament="MODUS",
            stage="Group A",
            player_a=SimpleNamespace(
                player_name="Player A",
            ),
            player_b=SimpleNamespace(
                player_name="Player B",
            ),
        )


class PredictionLaboratoryServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.registry = PredictionModelRegistry(
            models=[
                ("fake", FakeModel()),
            ],
            default_model="fake",
        )
        self.service = PredictionLaboratoryService(
            snapshot_engine=FakeSnapshotEngine(),
            model_registry=self.registry,
        )

    def test_analyse_match_builds_report(self):
        report = self.service.analyse_match(
            object(),
            123,
        )

        self.assertEqual(
            report.model_name,
            "fake",
        )
        self.assertEqual(
            report.model_version,
            "fake-v1",
        )
        self.assertEqual(
            report.match_id,
            123,
        )
        self.assertEqual(
            report.strongest_factors[0].feature,
            "overall",
        )
        self.assertEqual(
            report.opposing_factors[0].feature,
            "finishing",
        )


if __name__ == "__main__":
    unittest.main()
