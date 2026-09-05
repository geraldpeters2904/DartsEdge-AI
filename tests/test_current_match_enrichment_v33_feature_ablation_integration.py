import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_feature_ablation_service import (
    CurrentMatchEnrichmentV33FeatureAblationService,
)


class FakeAblationService(
    CurrentMatchEnrichmentV33FeatureAblationService
):

    def __init__(self):
        self.calls = []
        self.snapshot_calls = []

    def analyse(
        self,
        db,
        *,
        offset=0,
        limit=100,
        competition_code="MODUS",
    ):
        self._test_offset = offset
        self._test_limit = limit
        return super().analyse(
            db,
            offset=offset,
            limit=limit,
            competition_code=competition_code,
        )

    def _build_snapshot(
        self,
        db,
        match_id,
        competition_code,
    ):
        self.snapshot_calls.append(
            {
                "match_id": match_id,
                "competition_code": competition_code,
            }
        )
        return SimpleNamespace(match_id=match_id)

    def _evaluate_engine(
        self,
        db,
        *,
        engine,
        snapshots,
    ):
        names = tuple(
            feature.name
            for feature in engine.features
        )

        self.calls.append(
            {
                "model_version": engine.MODEL_VERSION,
                "feature_names": names,
                "offset": self._test_offset,
                "limit": self._test_limit,
                "competition_code": (
                    self.snapshot_calls[0]["competition_code"]
                    if self.snapshot_calls
                    else None
                ),
                "match_ids": tuple(
                    snapshot.match_id
                    for snapshot in snapshots
                ),
            }
        )

        if "scoring_power" in names:
            return {
                "accuracy": 62.0,
                "brier": 0.220,
                "log_loss": 0.640,
            }

        return {
            "accuracy": 58.0,
            "brier": 0.240,
            "log_loss": 0.680,
        }


class FakeQuery:

    def __init__(self):
        self._offset = 0
        self._limit = 100

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        return [
            (match_id,)
            for match_id in range(
                self._offset + 1,
                self._offset + self._limit + 1,
            )
        ]


class FakeDb:

    def query(self, *args):
        return FakeQuery()


class CurrentMatchEnrichmentV33FeatureAblationIntegrationTests(
    unittest.TestCase
):
    def test_analyse_uses_v33_and_same_historical_window(self):
        service = FakeAblationService()

        report = service.analyse(
            FakeDb(),
            offset=250,
            limit=100,
            competition_code="MODUS",
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            100,
        )

        self.assertGreater(
            len(service.calls),
            1,
        )

        for call in service.calls:
            self.assertEqual(
                call["model_version"],
                "transparent-v3.3",
            )
            self.assertEqual(
                call["offset"],
                250,
            )
            self.assertEqual(
                call["limit"],
                100,
            )
            self.assertEqual(
                call["competition_code"],
                "MODUS",
            )

    def test_zero_weight_v33_features_are_not_ablated(self):
        service = FakeAblationService()

        report = service.analyse(
            FakeDb(),
            offset=0,
            limit=100,
        )

        names = {
            item.feature_name
            for item in report.features
        }

        self.assertNotIn(
            "overall_strength",
            names,
        )

        self.assertNotIn(
            "recent_form",
            names,
        )

    def test_helpful_feature_receives_positive_importance(self):
        service = FakeAblationService()

        report = service.analyse(
            FakeDb(),
            offset=0,
            limit=100,
        )

        scoring = next(
            item
            for item in report.features
            if item.feature_name
            == "scoring_power"
        )

        self.assertGreater(
            scoring.accuracy_drop,
            0.0,
        )

        self.assertGreater(
            scoring.brier_increase,
            0.0,
        )

        self.assertGreater(
            scoring.log_loss_increase,
            0.0,
        )

        self.assertGreater(
            scoring.importance_score,
            0.0,
        )

        self.assertTrue(
            scoring.helpful,
        )

    def test_report_is_sorted_by_importance(self):
        service = FakeAblationService()

        report = service.analyse(
            FakeDb(),
            offset=0,
            limit=100,
        )

        importance = [
            item.importance_score
            for item in report.features
        ]

        self.assertEqual(
            importance,
            sorted(
                importance,
                reverse=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()
