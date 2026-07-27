import os
import tempfile
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import app
from app.models.match import Match
from app.services.prediction_centre_service import build_prediction_centre


class PredictionCentreUIRefinementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_upcoming_fixture_fallback(self):
        tomorrow = date.today() + timedelta(days=1)
        self.db.add(Match(date=tomorrow, player_a="Alpha", player_b="Beta", status="scheduled"))
        self.db.commit()
        payload = build_prediction_centre(self.db)
        self.assertEqual(payload["fixture_scope"], "upcoming")
        self.assertEqual(payload["fixture_count"], 1)
        self.assertEqual(payload["cards"][0]["fixture"].date, tomorrow)

    def test_today_takes_priority_over_future(self):
        self.db.add_all([
            Match(date=date.today(), player_a="Today A", player_b="Today B", status="scheduled"),
            Match(date=date.today() + timedelta(days=1), player_a="Future A", player_b="Future B", status="scheduled"),
        ])
        self.db.commit()
        payload = build_prediction_centre(self.db)
        self.assertEqual(payload["fixture_scope"], "today")
        self.assertEqual(payload["fixture_count"], 1)
        self.assertEqual(payload["cards"][0]["fixture"].player_a, "Today A")

    def test_fixture_beyond_seven_days_is_not_shown(self):
        self.db.add(Match(date=date.today() + timedelta(days=8), player_a="Alpha", player_b="Beta", status="scheduled"))
        self.db.commit()
        self.assertEqual(build_prediction_centre(self.db)["fixture_count"], 0)

    def test_template_uses_separate_kpi_elements(self):
        with open("app/templates/prediction_centre.html", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("prediction-kpi-label", text)
        self.assertIn("prediction-kpi-value", text)
        self.assertIn("{:,.2f}", text)
        self.assertIn("Manage fixture feed", text)

    def test_route_still_renders(self):
        response = TestClient(app).get("/prediction-centre")
        self.assertEqual(response.status_code, 200)
        self.assertIn("prediction-centre-kpis", response.text)


if __name__ == "__main__":
    unittest.main()
