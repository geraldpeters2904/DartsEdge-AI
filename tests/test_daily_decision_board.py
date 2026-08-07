import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.daily_decision_board_service import (
    build_daily_decision_board,
)


TEMPLATE = Path(
    "app/templates/decision_board.html"
)


class DailyDecisionBoardTests(
    unittest.TestCase
):
    def card(
        self,
        *,
        fixture_id,
        score,
        ev,
        edge,
    ):
        return {
            "fixture": SimpleNamespace(
                id=fixture_id,
                date="2026-08-07",
                tournament="MODUS",
                player_a=f"A{fixture_id}",
                player_b=f"B{fixture_id}",
            ),
            "opportunity": {
                "selection": f"A{fixture_id}",
                "probability": 62.0,
                "model_confidence": 78.0,
            },
            "assessment": SimpleNamespace(
                expected_value_percent=ev,
                edge_percent=edge,
                recommended_stake=12.0,
            ),
            "price": SimpleNamespace(
                bookmaker="Paddy Power",
                decimal_odds=2.0,
            ),
            "decision_intelligence": {
                "score": score,
                "grade": "Strong",
                "recommendation": "SMALL BET",
                "stars": 3,
                "strategy_suggested_stake": 10.0,
                "trust_score": 74,
                "evidence_score": 80,
                "market_direction": "shortening",
                "market_volatility": "low",
                "clv_percent": None,
                "positive_reasons": [
                    "Expected value is strong."
                ],
                "caution_reasons": [],
            },
        }

    @patch(
        "app.services.daily_decision_board_service.build_prediction_centre"
    )
    def test_ranks_by_decision_score_first(
        self,
        centre,
    ):
        centre.return_value = {
            "centre_date": "2026-08-07",
            "fixture_scope": "today",
            "fixture_count": 2,
            "decision_scored_count": 2,
            "cards": [
                self.card(
                    fixture_id=1,
                    score=72,
                    ev=15.0,
                    edge=10.0,
                ),
                self.card(
                    fixture_id=2,
                    score=85,
                    ev=8.0,
                    edge=7.0,
                ),
            ],
            "portfolio": {
                "available_bankroll": 1000.0,
                "open_exposure": 0.0,
                "exposure_percent": 0.0,
            },
            "active_strategy": {
                "name": "Paper Trading",
                "version": 4,
            },
            "decision_engine_active": False,
        }

        board = (
            build_daily_decision_board(
                object()
            )
        )

        self.assertEqual(
            board[
                "decisions"
            ][0].fixture_id,
            2,
        )

        self.assertEqual(
            board[
                "top_decision"
            ].decision_score,
            85,
        )

    def test_template_contains_decision_queue(self):
        text = TEMPLATE.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Decision Board",
            text,
        )

        self.assertIn(
            "Today’s Decision Queue",
            text,
        )

        self.assertIn(
            "Scored opportunities",
            text,
        )

    def test_route_registered(self):
        response = TestClient(
            app
        ).get(
            "/decision-board"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "Decision Board",
            response.text,
        )


if __name__ == "__main__":
    unittest.main()
