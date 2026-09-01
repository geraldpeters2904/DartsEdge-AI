import unittest
from datetime import date

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.bet_slip_item import BetSlipItem
from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.services.bet_slip_service import (
    add_bet_slip_item,
    confirm_as_paper_trade,
    update_bet_slip_stake,
)


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

    def test_update_stake(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="A",
            odds=2.0,
            stake=4,
        )

        updated = update_bet_slip_stake(
            self.db,
            item.id,
            7.5,
        )

        self.assertEqual(updated.stake, 7.5)

    def test_update_stake_rejects_non_positive_value(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="A",
            odds=2.0,
            stake=4,
        )

        with self.assertRaises(ValueError):
            update_bet_slip_stake(
                self.db,
                item.id,
                0,
            )

    def test_page_contains_editable_stake_form(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.0,
            stake=4,
            model_probability=61.5,
            expected_value=8.25,
            kelly_stake=6.5,
            strategy_name="transparent-v3.5",
        )

        response = self.client.get("/bet-slip")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Bookmaker", response.text)
        self.assertIn("Model %", response.text)
        self.assertIn("Suggested Stake", response.text)
        self.assertIn("Paddy Power", response.text)
        self.assertIn("61.5%", response.text)
        self.assertIn("+8.25%", response.text)
        self.assertIn("£6.50", response.text)
        self.assertIn("transparent-v3.5", response.text)
        self.assertIn(
            f'/bet-slip/{item.id}/stake',
            response.text,
        )
        self.assertIn('name="stake"', response.text)
        self.assertIn('value="4.00"', response.text)
        self.assertIn("Update", response.text)

    def test_update_stake_route(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="A",
            odds=2.0,
            stake=4,
        )

        response = self.client.post(
            f"/bet-slip/{item.id}/stake",
            data={"stake": 8.5},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.db.refresh(item)
        self.assertEqual(item.stake, 8.5)

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
