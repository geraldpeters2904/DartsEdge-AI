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
from app.services.prediction_centre_service import build_prediction_centre


class PredictionCentreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_empty_state_payload(self):
        data = build_prediction_centre(self.db)
        self.assertEqual(data['fixture_count'], 0)
        self.assertEqual(data['cards'], [])

    def test_today_fixture_is_included(self):
        self.db.add(Match(date=date.today(), player_a='Alpha', player_b='Beta', status='scheduled'))
        self.db.commit()
        data = build_prediction_centre(self.db)
        self.assertEqual(data['fixture_count'], 1)
        self.assertEqual(data['cards'][0]['fixture'].player_a, 'Alpha')

    def test_future_fixture_is_excluded(self):
        from datetime import timedelta
        self.db.add(Match(date=date.today()+timedelta(days=1), player_a='Alpha', player_b='Beta', status='scheduled'))
        self.db.commit()
        self.assertEqual(build_prediction_centre(self.db)['fixture_count'], 0)

    def test_template_has_workspace_sections(self):
        with open('app/templates/prediction_centre.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('Prediction Centre', text)
        self.assertIn('Expected value', text)
        self.assertIn('Suggested stake', text)

    def test_route_is_registered(self):
        client = TestClient(app)
        response = client.get('/prediction-centre')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Prediction Centre', response.text)


if __name__ == '__main__':
    unittest.main()
