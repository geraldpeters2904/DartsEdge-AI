import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import date

from fastapi.testclient import TestClient

from app.db import Base
from app.main import app
from app.models.match import Match
from app.services.daily_briefing_service import build_daily_briefing


class FakeQuery:
    def __init__(self, rows): self.rows = rows
    def filter(self, *args, **kwargs): return self
    def order_by(self, *args, **kwargs): return self
    def all(self): return self.rows


class FakeDB:
    def __init__(self, fixtures=None): self.fixtures = fixtures or []
    def query(self, model):
        if model is Match: return FakeQuery(self.fixtures)
        return FakeQuery([])


class DailyBriefingTests(unittest.TestCase):
    def test_route_is_registered(self):
        paths = {route.path for route in app.routes}
        self.assertIn('/daily-briefing', paths)

    def test_template_contains_briefing_heading(self):
        with open('app/templates/daily_briefing.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('Daily Intelligence Briefing', text)

    def test_template_uses_effective_stake_not_raw_value_stake(self):
        with open('app/templates/daily_briefing.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('decision_engine.effective_stake', text)
        self.assertNotIn('assessment.suggested_stake', text)

    def test_navigation_contains_briefing(self):
        with open('app/templates/base.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('/daily-briefing', text)

    def test_service_module_imports(self):
        from app.services.daily_briefing_service import build_daily_briefing as fn
        self.assertTrue(callable(fn))

    def test_page_returns_200(self):
        client = TestClient(app)
        response = client.get('/daily-briefing')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Daily Intelligence Briefing', response.text)


    @patch("app.services.daily_briefing_service.decide")
    @patch("app.services.daily_briefing_service.build_portfolio_health")
    @patch("app.services.daily_briefing_service.assess_value")
    @patch("app.services.daily_briefing_service._latest_fixture_price")
    @patch("app.services.daily_briefing_service.build_ranked_opportunities")
    @patch("app.services.daily_briefing_service.get_settings")
    def test_value_opportunity_uses_decision_engine_effective_stake(
        self,
        mock_settings,
        mock_ranked,
        mock_price,
        mock_assess,
        mock_portfolio,
        mock_decide,
    ):
        mock_settings.return_value = SimpleNamespace(
            bankroll=1000.0,
            kelly_fraction=0.25,
            max_daily_risk=10.0,
            minimum_edge=0.0,
        )
        mock_ranked.return_value = [{
            "match_id": 123,
            "probability": 62.0,
            "model_confidence": 78.0,
            "player_a_history_matches": 40,
            "player_b_history_matches": 35,
            "tournament": "MODUS",
            "selection": "Player A",
        }]
        mock_price.return_value = SimpleNamespace(
            decimal_odds=2.0,
            bookmaker="Paddy Power",
        )
        mock_assess.return_value = SimpleNamespace(
            model_probability=62.0,
            expected_value_percent=10.0,
            edge_percent=8.0,
            decimal_odds=2.0,
            recommended_stake=20.0,
            decision="Consider",
        )
        mock_portfolio.return_value = {
            "exposure_percent": 2.0,
        }
        mock_decide.return_value = SimpleNamespace(
            effective_stake=0.0,
            enforced=True,
            qualifies=False,
        )

        from app.services.daily_briefing_service import _value_opportunities

        db = FakeDB()
        rows = _value_opportunities(db, limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["assessment"].recommended_stake, 20.0)
        self.assertEqual(rows[0]["decision_engine"].effective_stake, 0.0)

        mock_decide.assert_called_once_with(
            db,
            official_decision="Consider",
            official_stake=20.0,
            model_probability=62.0,
            confidence_percent=78.0,
            expected_value_percent=10.0,
            edge_percent=8.0,
            decimal_odds=2.0,
            bankroll=1000.0,
            market="match_winner",
            competition="MODUS",
            sample_size=35,
            portfolio_exposure_percent=2.0,
        )


if __name__ == '__main__':
    unittest.main()
