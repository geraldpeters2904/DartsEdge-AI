import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.value_board_service import build_value_board


class ValueBoardServiceTests(unittest.TestCase):
    @patch(
        "app.services.value_board_service.context_to_opportunity"
    )
    @patch(
        "app.services.value_board_service.build_prediction_context"
    )
    @patch(
        "app.services.value_board_service.get_scheduled_fixtures"
    )
    def test_attaches_latest_paddy_power_match_odds(
        self,
        get_scheduled_fixtures,
        build_prediction_context,
        context_to_opportunity,
    ):
        fixture = SimpleNamespace(
            id=17620,
            date=None,
            tournament="MODUS Super Series",
            stage=None,
            match_format=None,
            player_a="Richard McKee",
            player_b="Martyn Turner",
        )

        get_scheduled_fixtures.return_value = [fixture]

        build_prediction_context.return_value = SimpleNamespace()

        context_to_opportunity.return_value = {
            "match_id": 17620,
            "date": None,
            "tournament": "MODUS Super Series",
            "player_a": "Richard McKee",
            "player_b": "Martyn Turner",
            "selection": "Martyn Turner",
            "probability": 50.86,
            "fair_odds": 1.97,
            "model_name": "transparent-v3.5",
            "model_version": "transparent-v3.5",
            "player_a_probability": 49.14,
            "player_b_probability": 50.86,
            "model_confidence": 70.516,
            "model_score": 53.0,
            "player_a_history_matches": 61,
            "player_b_history_matches": 164,
            "explanations": [],
            "contributions": [],
        }

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            SimpleNamespace(
                decimal_odds=2.1,
                bookmaker_code="paddypower",
            )
        )

        rows = build_value_board(db)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["selection"],
            "Martyn Turner",
        )
        self.assertEqual(
            rows[0]["probability"],
            50.86,
        )
        self.assertEqual(
            rows[0]["fair_odds"],
            1.97,
        )
        self.assertEqual(
            rows[0]["market_odds"],
            2.1,
        )
        self.assertEqual(
            rows[0]["bookmaker"],
            "Paddy Power",
        )
        self.assertEqual(
            rows[0]["edge"],
            3.24,
        )
        self.assertEqual(
            rows[0]["expected_value_percent"],
            6.81,
        )
        self.assertTrue(
            rows[0]["is_value_confirmed"],
        )
        self.assertEqual(
            rows[0]["status"],
            "Value confirmed",
        )
        self.assertEqual(
            rows[0]["action"],
            "Consider",
        )

    @patch(
        "app.services.value_board_service.context_to_opportunity"
    )
    @patch(
        "app.services.value_board_service.build_prediction_context"
    )
    @patch(
        "app.services.value_board_service.get_scheduled_fixtures"
    )
    def test_ranks_stronger_confirmed_value_ahead_of_win_probability(
        self,
        get_scheduled_fixtures,
        build_prediction_context,
        context_to_opportunity,
    ):
        fixtures = [
            SimpleNamespace(
                id=1,
                date=None,
                tournament="MODUS Super Series",
                stage=None,
                match_format=None,
                player_a="Player A",
                player_b="Player B",
            ),
            SimpleNamespace(
                id=2,
                date=None,
                tournament="MODUS Super Series",
                stage=None,
                match_format=None,
                player_a="Player C",
                player_b="Player D",
            ),
        ]
        get_scheduled_fixtures.return_value = fixtures
        build_prediction_context.side_effect = [
            SimpleNamespace(),
            SimpleNamespace(),
        ]
        context_to_opportunity.side_effect = [
            {
                "selection": "Player A",
                "probability": 65.0,
                "fair_odds": 1.54,
            },
            {
                "selection": "Player C",
                "probability": 55.0,
                "fair_odds": 1.82,
            },
        ]

        db = MagicMock()
        query = db.query.return_value
        filtered = query.filter.return_value
        ordered = filtered.order_by.return_value
        ordered.first.side_effect = [
            SimpleNamespace(
                decimal_odds=1.60,
                bookmaker_code="paddypower",
            ),
            SimpleNamespace(
                decimal_odds=2.20,
                bookmaker_code="paddypower",
            ),
        ]

        rows = build_value_board(db)

        self.assertEqual(
            [row["fixture_id"] for row in rows],
            [2, 1],
        )
        self.assertGreater(
            rows[0]["expected_value_percent"],
            rows[1]["expected_value_percent"],
        )



if __name__ == "__main__":
    unittest.main()
