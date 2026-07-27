import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.bet_slip_item import BetSlipItem
from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.services.bet_slip_service import add_bet_slip_item, confirm_as_paper_trade


class BetSlipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(BetSlipItem).delete()
        self.db.commit()
        self.fixture = Match(player_a="Slip Alpha", player_b="Slip Beta", date=date.today(), status="scheduled", tournament="TEST")
        self.db.add(self.fixture); self.db.commit(); self.db.refresh(self.fixture)

    def tearDown(self):
        self.db.query(BetSlipItem).delete()
        self.db.query(Match).filter(Match.tournament == "TEST").delete()
        self.db.commit(); self.db.close()

    def test_add_and_list_api(self):
        response = self.client.post('/bet-slip/add', data={'fixture_id': self.fixture.id, 'selection': 'Slip Alpha', 'odds': 2.1, 'stake': 5}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        payload = self.client.get('/api/bet-slip').json()
        self.assertEqual(payload['summary']['count'], 1)

    def test_duplicate_updates_instead_of_duplicating(self):
        add_bet_slip_item(self.db, fixture_id=self.fixture.id, market='Match Winner', selection='Slip Alpha', bookmaker='A', odds=2.0, stake=4)
        add_bet_slip_item(self.db, fixture_id=self.fixture.id, market='Match Winner', selection='Slip Alpha', bookmaker='B', odds=2.2, stake=6)
        self.assertEqual(self.db.query(BetSlipItem).count(), 1)
        self.assertEqual(self.db.query(BetSlipItem).first().stake, 6)

    def test_invalid_selection_rejected(self):
        with self.assertRaises(ValueError):
            add_bet_slip_item(self.db, fixture_id=self.fixture.id, market='Match Winner', selection='Other', bookmaker='A', odds=2, stake=1)

    def test_confirm_creates_open_paper_trade(self):
        item, _ = add_bet_slip_item(self.db, fixture_id=self.fixture.id, market='Match Winner', selection='Slip Alpha', bookmaker='A', odds=2, stake=3, model_probability=60)
        trade = confirm_as_paper_trade(self.db, item.id)
        self.assertEqual(trade.status, 'OPEN')
        self.assertEqual(trade.stake, 3)
        self.db.query(PaperTrade).filter(PaperTrade.id == trade.id).delete(); self.db.commit()

    def test_page_loads(self):
        self.assertEqual(self.client.get('/bet-slip').status_code, 200)


if __name__ == '__main__':
    unittest.main()
