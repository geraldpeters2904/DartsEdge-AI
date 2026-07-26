import unittest
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


if __name__ == '__main__':
    unittest.main()
