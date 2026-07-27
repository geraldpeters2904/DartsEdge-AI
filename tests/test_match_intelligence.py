import os
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import app
from app.models.match import Match
from app.models.player import Player
from app.models.player_stats import PlayerStats
from app.services.match_intelligence_workspace_service import build_match_intelligence


class MatchIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        a = Player(name='Alpha', elo=1550, average=91.0, checkout=38.0)
        b = Player(name='Beta', elo=1480, average=87.0, checkout=34.0)
        self.db.add_all([a, b])
        self.db.commit()
        self.db.add_all([
            PlayerStats(player_id=a.id, matches=10, wins=7, losses=3, legs_won=30, legs_lost=20),
            PlayerStats(player_id=b.id, matches=10, wins=4, losses=6, legs_won=22, legs_lost=28),
        ])
        self.fixture = Match(date=date.today(), player_a='Alpha', player_b='Beta', status='scheduled')
        self.db.add(self.fixture)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_builds_fixture_workspace(self):
        data = build_match_intelligence(self.db, self.fixture.id)
        self.assertIsNotNone(data)
        self.assertEqual(data['fixture'].player_a, 'Alpha')
        self.assertEqual(data['selected_player'], 'Alpha')

    def test_missing_fixture_returns_none(self):
        self.assertIsNone(build_match_intelligence(self.db, 999999))

    def test_profiles_are_included(self):
        data = build_match_intelligence(self.db, self.fixture.id)
        self.assertEqual(data['profile_a']['matches'], 10)
        self.assertEqual(data['profile_b']['matches'], 10)

    def test_template_contains_intelligence_sections(self):
        with open('app/templates/match_intelligence.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('Why this prediction?', text)
        self.assertIn('Historical matchup', text)
        self.assertIn('Strategy context', text)

    def test_route_is_registered(self):
        client = TestClient(app)
        response = client.get('/match-intelligence/999999')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
