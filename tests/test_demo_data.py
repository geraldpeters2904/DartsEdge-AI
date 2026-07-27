import os
import tempfile
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import app
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.models.player import Player
from app.services.demo_data_service import demo_summary, load_demo_data, reset_demo_data


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        os.unlink(self.tmp.name)

    def test_load_creates_expected_demo_records(self):
        result = load_demo_data(self.db)
        self.assertEqual(result["players"], 8)
        self.assertEqual(result["fixtures"], 14)
        self.assertEqual(result["odds"], 56)

    def test_load_is_duplicate_safe(self):
        load_demo_data(self.db)
        second = load_demo_data(self.db)
        self.assertEqual(second["created_players"], 0)
        self.assertEqual(second["created_fixtures"], 0)
        self.assertEqual(second["created_odds"], 0)

    def test_reset_removes_only_demo_records(self):
        self.db.add(Player(name="Real Player", elo=1500, average=90, checkout=35, one80_rate=0.3))
        self.db.add(Match(player_a="Real Player", player_b="Other", tournament="MODUS"))
        self.db.commit()
        load_demo_data(self.db)
        reset_demo_data(self.db)
        self.assertEqual(demo_summary(self.db), {"players": 0, "fixtures": 0, "odds": 0})
        self.assertIsNotNone(self.db.query(Player).filter(Player.name == "Real Player").first())
        self.assertIsNotNone(self.db.query(Match).filter(Match.tournament == "MODUS").first())

    def test_fixture_dates_cover_current_week(self):
        load_demo_data(self.db)
        dates = {row.date for row in self.db.query(Match).filter(Match.tournament == "DEMO Showcase").all()}
        self.assertEqual(len(dates), 7)

    def test_admin_page_and_api_render(self):
        client = TestClient(app)
        self.assertEqual(client.get("/admin/demo-data").status_code, 200)
        payload = client.get("/api/demo-data").json()
        self.assertTrue(payload["demo"])


if __name__ == "__main__":
    unittest.main()
