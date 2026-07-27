import os
import tempfile
import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.prediction_centre_service import build_prediction_centre


class PredictionCentreInteractiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        engine = create_engine(f"sqlite:///{self.tmp.name}")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmp.name)

    def test_competitions_are_exposed_for_filtering(self):
        self.db.add_all([
            Match(date=date.today(), player_a='A', player_b='B', tournament='DEMO Alpha', status='scheduled'),
            Match(date=date.today(), player_a='C', player_b='D', tournament='DEMO Beta', status='scheduled'),
        ])
        self.db.commit()
        payload = build_prediction_centre(self.db)
        self.assertEqual(payload['competitions'], ['DEMO Alpha', 'DEMO Beta'])

    def test_cards_include_sort_values(self):
        self.db.add(Match(date=date.today(), player_a='A', player_b='B', status='scheduled'))
        self.db.commit()
        card = build_prediction_centre(self.db)['cards'][0]
        for key in ('sort_probability', 'sort_ev', 'sort_edge', 'sort_stake'):
            self.assertIn(key, card)

    def test_template_contains_filter_controls(self):
        with open('app/templates/prediction_centre.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('pc-competition', text)
        self.assertIn('pc-status', text)
        self.assertIn('pc-sort', text)
        self.assertIn('pc-positive-only', text)

    def test_template_contains_fixture_data_attributes(self):
        with open('app/templates/prediction_centre.html', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('data-competition', text)
        self.assertIn('data-probability', text)
        self.assertIn('data-ev', text)
        self.assertIn('data-stake', text)

    def test_styles_include_responsive_filter_grid(self):
        with open('app/static/css/styles.css', encoding='utf-8') as handle:
            text = handle.read()
        self.assertIn('.prediction-filter-grid', text)
        self.assertIn('.prediction-centre-card[hidden]', text)


if __name__ == '__main__':
    unittest.main()
