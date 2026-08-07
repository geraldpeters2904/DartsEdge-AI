import unittest
from types import SimpleNamespace

from app.services.prediction_evidence_service import (
    build_prediction_evidence,
    evidence_summary,
)


def opportunity():
    return {
        "probability": 60.8,
        "model_confidence": 76.0,
        "player_a_history_matches": 147,
        "player_b_history_matches": 92,
        "contributions": [
            {
                "feature": "scoring_power",
                "label": "Scoring Power",
                "weighted_score": 0.021,
            },
            {
                "feature": "finishing_strength",
                "label": "Finishing Strength",
                "weighted_score": -0.010,
            },
        ],
    }


class PredictionEvidenceServiceTests(
    unittest.TestCase
):
    def test_builds_complete_evidence(self):
        evidence = (
            build_prediction_evidence(
                opportunity=opportunity(),
                trust_report=(
                    SimpleNamespace(
                        trust_score=74
                    )
                ),
                stability_report=(
                    SimpleNamespace(
                        stability_score=86,
                        most_sensitive_feature=(
                            "scoring_rating"
                        ),
                    )
                ),
                assessment=(
                    SimpleNamespace(
                        edge_percent=8.2,
                        expected_value_percent=(
                            11.4
                        ),
                    )
                ),
            )
        )

        self.assertGreaterEqual(
            evidence.evidence_score,
            60,
        )
        self.assertEqual(
            evidence.trust_score,
            74,
        )
        self.assertEqual(
            evidence.stability_score,
            86,
        )
        self.assertEqual(
            evidence.strongest_feature,
            "Scoring Power",
        )
        self.assertEqual(
            evidence.most_sensitive_feature,
            "Scoring Rating",
        )

    def test_missing_market_data_creates_caution(self):
        evidence = (
            build_prediction_evidence(
                opportunity=opportunity(),
                trust_report=None,
                stability_report=None,
                assessment=None,
            )
        )

        self.assertIn(
            "Market odds are required to confirm value.",
            evidence.caution_reasons,
        )
        self.assertIn(
            "Model trust is not currently available.",
            evidence.caution_reasons,
        )

    def test_uses_lower_player_history(self):
        item = opportunity()
        item[
            "player_a_history_matches"
        ] = 100
        item[
            "player_b_history_matches"
        ] = 8

        evidence = (
            build_prediction_evidence(
                opportunity=item,
            )
        )

        self.assertEqual(
            evidence.historical_matches,
            8,
        )
        self.assertIn(
            "At least one player has limited historical coverage.",
            evidence.caution_reasons,
        )

    def test_summary_is_json_ready(self):
        evidence = (
            build_prediction_evidence(
                opportunity=opportunity(),
            )
        )

        payload = evidence_summary(
            evidence
        )

        self.assertIsInstance(
            payload["breakdown"],
            dict,
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


if __name__ == "__main__":
    unittest.main()
