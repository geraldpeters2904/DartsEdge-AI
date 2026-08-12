import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)


def _fixture(
    fixture_id,
    *,
    player_a="Alpha",
    player_b="Bravo",
):
    return SimpleNamespace(
        id=fixture_id,
        player_a=player_a,
        player_b=player_b,
        tournament="MODUS Super Series",
    )


class LiveOpportunityPipelineReadinessTests(
    unittest.TestCase
):
    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_live_opportunity_centre"
    )
    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_prediction_centre"
    )
    def test_waiting_when_no_fixtures(
        self,
        prediction,
        live,
    ):
        prediction.return_value = {
            "cards": [],
        }

        live.return_value = {
            "opportunities": (),
        }

        result = (
            build_live_opportunity_pipeline_readiness(
                SimpleNamespace(),
            )
        )

        self.assertEqual(
            result.state,
            "WAITING_FOR_FIXTURES",
        )

        self.assertEqual(
            result.fixture_count,
            0,
        )

    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_live_opportunity_centre"
    )
    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_prediction_centre"
    )
    def test_waiting_for_odds(
        self,
        prediction,
        live,
    ):
        prediction.return_value = {
            "cards": [
                {
                    "fixture": _fixture(1),
                    "opportunity": {
                        "selection": "Alpha",
                    },
                    "price": None,
                    "assessment": None,
                    "decision_intelligence": None,
                },
            ],
        }

        live.return_value = {
            "opportunities": (),
        }

        result = (
            build_live_opportunity_pipeline_readiness(
                SimpleNamespace(),
            )
        )

        self.assertEqual(
            result.state,
            "WAITING_FOR_ODDS",
        )

        self.assertEqual(
            result.opportunity_count,
            1,
        )

        self.assertEqual(
            result.priced_count,
            0,
        )

        self.assertEqual(
            result.fixtures[0].state,
            "WAITING_FOR_ODDS",
        )

    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_live_opportunity_centre"
    )
    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_prediction_centre"
    )
    def test_waiting_for_decision_intelligence(
        self,
        prediction,
        live,
    ):
        prediction.return_value = {
            "cards": [
                {
                    "fixture": _fixture(2),
                    "opportunity": {
                        "selection": "Alpha",
                    },
                    "price": SimpleNamespace(
                        decimal_odds=1.90,
                    ),
                    "assessment": SimpleNamespace(
                        expected_value_percent=4.0,
                    ),
                    "decision_intelligence": None,
                },
            ],
        }

        live.return_value = {
            "opportunities": (),
        }

        result = (
            build_live_opportunity_pipeline_readiness(
                SimpleNamespace(),
            )
        )

        self.assertEqual(
            result.state,
            "WAITING_FOR_DECISION_INTELLIGENCE",
        )

        self.assertEqual(
            result.assessment_count,
            1,
        )

        self.assertEqual(
            result.decision_count,
            0,
        )

    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_live_opportunity_centre"
    )
    @patch(
        "app.services."
        "live_opportunity_pipeline_readiness_service."
        "build_prediction_centre"
    )
    def test_ready_when_live_opportunity_exists(
        self,
        prediction,
        live,
    ):
        prediction.return_value = {
            "cards": [
                {
                    "fixture": _fixture(3),
                    "opportunity": {
                        "selection": "Alpha",
                    },
                    "price": SimpleNamespace(
                        decimal_odds=2.0,
                    ),
                    "assessment": SimpleNamespace(
                        expected_value_percent=5.0,
                    ),
                    "decision_intelligence": {
                        "score": 82,
                    },
                },
            ],
        }

        live.return_value = {
            "opportunities": (
                SimpleNamespace(
                    fixture_id=3,
                ),
            ),
        }

        result = (
            build_live_opportunity_pipeline_readiness(
                SimpleNamespace(),
            )
        )

        self.assertEqual(
            result.state,
            "READY",
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.live_opportunity_count,
            1,
        )

        self.assertTrue(
            result.fixtures[
                0
            ].has_live_opportunity
        )


if __name__ == "__main__":
    unittest.main()
