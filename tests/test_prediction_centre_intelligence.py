import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.prediction_centre_service import (
    _card_intelligence,
)


class PredictionCentreIntelligenceTests(
    unittest.TestCase
):
    def test_reuses_prediction_context_snapshot(self):
        context = SimpleNamespace(
            snapshot=object()
        )

        opportunity = {
            "probability": 61.0,
            "model_confidence": 77.0,
            "player_a_history_matches": 40,
            "player_b_history_matches": 35,
            "contributions": [],
            "_prediction_context": context,
        }

        stability_report = (
            SimpleNamespace(
                match_id=123,
                model_version=(
                    "transparent-v3.3"
                ),
                player_a_name="Alpha",
                player_b_name="Bravo",
                base_probability=61.0,
                base_winner="Alpha",
                simulation_count=10,
                mean_probability=61.0,
                minimum_probability=60.0,
                maximum_probability=62.0,
                probability_range=2.0,
                standard_deviation=0.5,
                winner_change_count=0,
                stability_score=86,
                stability_grade="Strong",
                most_sensitive_feature=(
                    "scoring_rating"
                ),
                sensitivities=(),
                positive_reasons=(),
                caution_reasons=(),
            )
        )

        evidence = (
            SimpleNamespace(
                evidence_score=80,
                evidence_grade="Strong",
                model_probability=61.0,
                model_confidence=77.0,
                trust_score=74,
                stability_score=86,
                historical_matches=35,
                edge_percent=None,
                expected_value_percent=None,
                strongest_feature=None,
                most_sensitive_feature=(
                    "Scoring Rating"
                ),
                breakdown=SimpleNamespace(
                    model_quality=70.0,
                    trust_quality=74.0,
                    stability_quality=86.0,
                    history_quality=75.0,
                    value_quality=40.0,
                ),
                positive_reasons=(),
                caution_reasons=(),
            )
        )

        with patch(
            "app.services."
            "prediction_centre_service."
            "analyse_snapshot_stability",
            return_value=(
                stability_report
            ),
        ) as stability_mock, patch(
            "app.services."
            "prediction_centre_service."
            "build_prediction_evidence",
            return_value=evidence,
        ):
            stability, payload = (
                _card_intelligence(
                    opportunity=opportunity,
                    assessment=None,
                    trust_report=(
                        SimpleNamespace(
                            trust_score=74
                        )
                    ),
                )
            )

        stability_mock.assert_called_once_with(
            context.snapshot
        )

        self.assertEqual(
            stability[
                "stability_score"
            ],
            86,
        )

        self.assertEqual(
            payload[
                "evidence_score"
            ],
            80,
        )


if __name__ == "__main__":
    unittest.main()
