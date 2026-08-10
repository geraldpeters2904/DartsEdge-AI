import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_challenger_service import (
    CurrentMatchEnrichmentV33ChallengerService,
    V33ChallengerConfiguration,
)


class FakeLaboratory:
    last_model_names = None
    last_match_ids = None
    last_competition_code = None

    def __init__(
        self,
        *,
        model_registry,
    ):
        self.model_registry = model_registry

    def compare_models(
        self,
        db,
        *,
        model_names,
        match_ids,
        competition_code,
    ):
        names = tuple(model_names)

        FakeLaboratory.last_model_names = names
        FakeLaboratory.last_match_ids = tuple(
            match_ids
        )
        FakeLaboratory.last_competition_code = (
            competition_code
        )

        values = {
            "baseline-v3.3": (
                60.0,
                0.250,
                0.700,
            ),
            "challenger-a": (
                60.5,
                0.245,
                0.690,
            ),
            "challenger-b": (
                57.0,
                0.240,
                0.680,
            ),
            "challenger-c": (
                60.0,
                0.255,
                0.710,
            ),
        }

        summaries = []

        for name in names:
            accuracy, brier, log_loss = (
                values[name]
            )

            registered = (
                self.model_registry
                .get_registered(name)
            )

            summaries.append(
                SimpleNamespace(
                    model_name=name,
                    model_version=(
                        registered.version
                    ),
                    matches_evaluated=100,
                    accuracy=accuracy,
                    average_brier_score=brier,
                    average_log_loss=log_loss,
                )
            )

        return SimpleNamespace(
            summaries=tuple(
                summaries
            )
        )


class CurrentMatchEnrichmentV33ChallengerIntegrationTests(
    unittest.TestCase
):
    @patch(
        "app.services.current_match_enrichment_v33_challenger_service."
        "ModelPerformanceLaboratory",
        FakeLaboratory,
    )
    @patch(
        "app.services.current_match_enrichment_v33_challenger_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103],
    )
    def test_baseline_and_challengers_share_same_historical_sample(
        self,
        selector,
    ):
        service = (
            CurrentMatchEnrichmentV33ChallengerService()
        )

        report = service.compare(
            object(),
            challengers=(
                V33ChallengerConfiguration(
                    name="challenger-a",
                    weights={
                        "recent_win_rate": 0.04,
                    },
                ),
                V33ChallengerConfiguration(
                    name="challenger-b",
                    weights={
                        "finishing_strength": 0.08,
                    },
                ),
                V33ChallengerConfiguration(
                    name="challenger-c",
                    weights={
                        "recent_win_rate": 0.04,
                        "finishing_strength": 0.08,
                    },
                ),
            ),
            offset=500,
            limit=100,
            competition_code="MODUS",
        )

        selector.assert_called_once()

        self.assertEqual(
            FakeLaboratory.last_match_ids,
            (101, 102, 103),
        )

        self.assertEqual(
            FakeLaboratory.last_model_names,
            (
                "baseline-v3.3",
                "challenger-a",
                "challenger-b",
                "challenger-c",
            ),
        )

        self.assertEqual(
            FakeLaboratory.last_competition_code,
            "MODUS",
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.matches_evaluated,
            100,
        )

    @patch(
        "app.services.current_match_enrichment_v33_challenger_service."
        "ModelPerformanceLaboratory",
        FakeLaboratory,
    )
    @patch(
        "app.services.current_match_enrichment_v33_challenger_service."
        "CurrentMatchEnrichmentV33ValidationService._select_match_ids",
        return_value=[101, 102, 103],
    )
    def test_acceptance_rule_selects_probability_safe_challenger(
        self,
        selector,
    ):
        service = (
            CurrentMatchEnrichmentV33ChallengerService()
        )

        report = service.compare(
            object(),
            challengers=(
                V33ChallengerConfiguration(
                    name="challenger-a",
                    weights={
                        "recent_win_rate": 0.04,
                    },
                ),
                V33ChallengerConfiguration(
                    name="challenger-b",
                    weights={
                        "finishing_strength": 0.08,
                    },
                ),
                V33ChallengerConfiguration(
                    name="challenger-c",
                    weights={
                        "recent_win_rate": 0.04,
                        "finishing_strength": 0.08,
                    },
                ),
            ),
            offset=500,
            limit=100,
        )

        results = {
            item.name: item
            for item in report.challengers
        }

        self.assertTrue(
            results[
                "challenger-a"
            ].accepted
        )

        # Better probability metrics but
        # a 3-point accuracy loss is rejected.
        self.assertFalse(
            results[
                "challenger-b"
            ].accepted
        )

        # Worse probability metrics are rejected.
        self.assertFalse(
            results[
                "challenger-c"
            ].accepted
        )

        self.assertEqual(
            report.best_accepted_challenger,
            "challenger-a",
        )


if __name__ == "__main__":
    unittest.main()
