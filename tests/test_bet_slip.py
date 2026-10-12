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
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="A",
            odds=2,
            stake=3,
            model_probability=60,
            expected_value=8.25,
            kelly_stake=6.5,
            strategy_name="transparent-v3.5",
        )
        trade = confirm_as_paper_trade(self.db, item.id)

        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.fixture_id, self.fixture.id)
        self.assertEqual(trade.stake, 3)
        self.assertEqual(trade.model_probability, 60)
        self.assertEqual(trade.expected_value, 8.25)
        self.assertEqual(trade.suggested_stake, 6.5)
        self.assertEqual(trade.strategy_name, "transparent-v3.5")

        self.db.query(PaperTrade).filter(
            PaperTrade.id == trade.id
        ).delete()
        self.db.commit()

    def test_add_accepts_canonical_handicap_selection(self):
        item, created = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Handicap",
            selection="Slip Alpha -1.5",
            bookmaker="A",
            odds=2.0,
            stake=4,
        )

        self.assertTrue(created)
        self.assertEqual(item.fixture_id, self.fixture.id)
        self.assertEqual(item.market, "Handicap")
        self.assertEqual(item.selection, "Slip Alpha -1.5")

    def test_confirm_preserves_handicap_selection_and_fixture(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Handicap",
            selection="Slip Beta +2.5",
            bookmaker="A",
            odds=1.9,
            stake=3,
            model_probability=58,
        )

        trade = confirm_as_paper_trade(self.db, item.id)

        self.assertEqual(trade.status, "OPEN")
        self.assertEqual(trade.fixture_id, self.fixture.id)
        self.assertEqual(trade.market, "Handicap")
        self.assertEqual(trade.selection, "Slip Beta +2.5")

        self.db.query(PaperTrade).filter(
            PaperTrade.id == trade.id
        ).delete()
        self.db.commit()

    def test_handicap_confirmation_fallback_prediction_uses_fixture_player(self):
        from app.models.prediction import Prediction

        self.db.query(Prediction).filter(
            Prediction.player_a == self.fixture.player_a,
            Prediction.player_b == self.fixture.player_b,
        ).delete()
        self.db.commit()

        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Handicap",
            selection="Slip Beta +2.5",
            bookmaker="A",
            odds=1.9,
            stake=3,
            model_probability=58,
        )

        trade = confirm_as_paper_trade(self.db, item.id)
        prediction = self.db.query(Prediction).filter(
            Prediction.id == trade.prediction_id
        ).first()

        self.assertIn(
            prediction.predicted_winner,
            {self.fixture.player_a, self.fixture.player_b},
        )
        self.assertNotEqual(
            prediction.predicted_winner,
            "Slip Beta +2.5",
        )

        self.db.query(PaperTrade).filter(
            PaperTrade.id == trade.id
        ).delete()
        self.db.query(Prediction).filter(
            Prediction.id == prediction.id
        ).delete()
        self.db.commit()

    def test_handicap_selection_without_line_rejected(self):
        with self.assertRaises(ValueError):
            add_bet_slip_item(
                self.db,
                fixture_id=self.fixture.id,
                market="Handicap",
                selection="Slip Alpha",
                bookmaker="A",
                odds=2.0,
                stake=1,
            )

    def test_handicap_selection_for_non_participant_rejected(self):
        with self.assertRaises(ValueError):
            add_bet_slip_item(
                self.db,
                fixture_id=self.fixture.id,
                market="Handicap",
                selection="Other -1.5",
                bookmaker="A",
                odds=2.0,
                stake=1,
            )

    def test_page_loads(self):
        self.assertEqual(self.client.get('/bet-slip').status_code, 200)


if __name__ == '__main__':
    unittest.main()


class BetSlipAuthorisationTests(unittest.TestCase):
    setUpClass = classmethod(BetSlipTests.setUpClass.__func__)
    setUp = BetSlipTests.setUp
    tearDown = BetSlipTests.tearDown


    def test_manual_stake_edit_marks_override(self):
        from app.services.bet_slip_service import update_bet_slip_stake

        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.0,
            stake=5.0,
        )

        self.assertEqual(item.stake_source, "unverified")

        updated = update_bet_slip_stake(self.db, item.id, 12.0)

        self.assertEqual(updated.stake, 12.0)
        self.assertEqual(updated.stake_source, "manual_override")


    def test_paper_trade_preserves_manual_override(self):
        from app.services.bet_slip_service import (
            update_bet_slip_stake,
            confirm_as_paper_trade,
        )

        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.0,
            stake=5.0,
            kelly_stake=5.0,
        )

        updated = update_bet_slip_stake(self.db, item.id, 12.0)
        trade = confirm_as_paper_trade(self.db, updated.id)

        self.assertEqual(trade.stake, 12.0)
        self.assertEqual(trade.suggested_stake, 5.0)
        self.assertEqual(trade.stake_source, "manual_override")


    def test_duplicate_submission_clears_previous_authorisation(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.0,
            stake=5.0,
        )

        # Simulate an existing server-authorised recommendation.
        item.stake_source = "authorised"
        self.db.commit()

        updated, created = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.2,
            stake=20.0,
        )

        self.assertFalse(created)
        self.assertEqual(updated.id, item.id)
        self.assertEqual(updated.stake, 20.0)
        self.assertEqual(updated.stake_source, "unverified")


    def test_value_board_leg_handicap_selection(self):
        item, created = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Leg Handicap",
            selection="Slip Alpha -1.5",
            bookmaker="Paddy Power",
            odds=2.1,
            stake=5.0,
        )

        self.assertTrue(created)
        self.assertEqual(item.market, "Leg Handicap")
        self.assertEqual(item.selection, "Slip Alpha -1.5")
        self.assertEqual(item.stake_source, "unverified")

        with self.assertRaises(ValueError):
            add_bet_slip_item(
                self.db,
                fixture_id=self.fixture.id,
                market="Leg Handicap",
                selection="Other -1.5",
                bookmaker="Paddy Power",
                odds=2.1,
                stake=5.0,
            )


    def test_value_board_additional_markets(self):
        valid_cases = [
            ("Most 180s", "Slip Alpha Most 180s"),
            ("Total Legs", "Over 7.5 Total Legs"),
            ("Total 180s", "Under 4.5 Total 180s"),
            ("Player Total 180s", "Slip Alpha Over 2.5 180s"),
        ]

        for market, selection in valid_cases:
            with self.subTest(market=market):
                item, created = add_bet_slip_item(
                    self.db,
                    fixture_id=self.fixture.id,
                    market=market,
                    selection=selection,
                    bookmaker="Paddy Power",
                    odds=2.1,
                    stake=5.0,
                )
                self.assertTrue(created)
                self.assertEqual(item.selection, selection)
                self.assertEqual(item.stake_source, "unverified")

        invalid_cases = [
            ("Most 180s", "Other Most 180s"),
            ("Total Legs", "Over -1.5 Total Legs"),
            ("Total 180s", "Under 0 Total 180s"),
            ("Player Total 180s", "Other Over 2.5 180s"),
        ]

        for market, selection in invalid_cases:
            with self.subTest(market=market, selection=selection):
                with self.assertRaises(ValueError):
                    add_bet_slip_item(
                        self.db,
                        fixture_id=self.fixture.id,
                        market=market,
                        selection=selection,
                        bookmaker="Paddy Power",
                        odds=2.1,
                        stake=5.0,
                    )








    def test_route_duplicate_submission_clears_authorisation(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.1,
            stake=5.0,
        )

        item.stake_source = "authorised"
        self.db.commit()

        response = self.client.post(
            "/bet-slip/add",
            data={
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "bookmaker": "Paddy Power",
                "odds": 2.1,
                "stake": 10.0,
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)

        self.db.expire_all()
        updated = self.db.query(BetSlipItem).filter(
            BetSlipItem.id == item.id
        ).one()

        self.assertEqual(updated.stake, 10.0)
        self.assertEqual(updated.stake_source, "unverified")
        self.assertEqual(
            self.db.query(BetSlipItem).filter(
                BetSlipItem.fixture_id == self.fixture.id
            ).count(),
            1,
        )

    def test_shadow_mode_rejection_remains_unverified(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            token = sign_recommendation(
                fixture_id=self.fixture.id,
                market="Match Winner",
                selection="Slip Alpha",
                odds=2.1,
                effective_stake=5.0,
            )
            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "market_odds": 2.1,
                "effective_stake": 5.0,
                "decision_engine": SimpleNamespace(
                    qualifies=False,
                    enforced=False,
                    effective_stake=5.0,
                ),
            }

            with patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "odds": 2.1,
                        "stake": 5.0,
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake_source, "unverified")
        self.assertEqual(item.stake, 5.0)

    def test_authorised_recommendation_ignores_forged_model_figures(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            token = sign_recommendation(
                fixture_id=self.fixture.id,
                market="Match Winner",
                selection="Slip Alpha",
                odds=2.1,
                effective_stake=5.0,
            )
            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "bookmaker": "Paddy Power",
                "market_odds": 2.1,
                "effective_stake": 5.0,
                "probability": 65.0,
                "expected_value_percent": 12.5,
                "kelly_stake": 6.0,
                "decision_engine": SimpleNamespace(qualifies=True),
            }

            with patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "bookmaker": "Fake Bookmaker",
                        "odds": 2.1,
                        "stake": 5.0,
                        "model_probability": 99.0,
                        "expected_value": 999.0,
                        "kelly_stake": 500.0,
                        "strategy_name": "Fake Strategy",
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake_source, "authorised")
        self.assertEqual(item.bookmaker, "Paddy Power")
        self.assertAlmostEqual(item.model_probability, 65.0)
        self.assertAlmostEqual(item.expected_value, 12.5)
        self.assertAlmostEqual(item.kelly_stake, 6.0)
        self.assertEqual(item.strategy_name, "Daily Value Board")

    def test_expired_recommendation_remains_unverified(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            with patch(
                "app.services.recommendation_signing_service.time.time",
                return_value=100000,
            ):
                token = sign_recommendation(
                    fixture_id=self.fixture.id,
                    market="Match Winner",
                    selection="Slip Alpha",
                    odds=2.1,
                    effective_stake=5.0,
                )

            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "market_odds": 2.1,
                "effective_stake": 5.0,
                "decision_engine": SimpleNamespace(qualifies=True),
            }

            with patch(
                "app.services.recommendation_signing_service.time.time",
                return_value=101000,
            ), patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "odds": 2.1,
                        "stake": 5.0,
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake_source, "unverified")

    def test_signed_recommendation_rejects_tampered_stake(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            token = sign_recommendation(
                fixture_id=self.fixture.id,
                market="Match Winner",
                selection="Slip Alpha",
                odds=2.1,
                effective_stake=5.0,
            )
            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "market_odds": 2.1,
                "effective_stake": 5.0,
                "decision_engine": SimpleNamespace(qualifies=True),
            }

            with patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "odds": 2.1,
                        "stake": 50.0,
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake, 50.0)
        self.assertEqual(item.stake_source, "unverified")

    def test_signed_currently_approved_recommendation_is_authorised(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            token = sign_recommendation(
                fixture_id=self.fixture.id,
                market="Match Winner",
                selection="Slip Alpha",
                odds=2.1,
                effective_stake=5.0,
            )
            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "bookmaker": "Paddy Power",
                "market_odds": 2.1,
                "effective_stake": 5.0,
                "probability": 65.0,
                "expected_value_percent": 36.5,
                "kelly_stake": 5.0,
                "decision_engine": SimpleNamespace(
                    qualifies=True,
                    effective_stake=5.0,
                    effective_decision="Accept",
                ),
            }

            with patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "bookmaker": "Paddy Power",
                        "odds": 2.1,
                        "stake": 5.0,
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake_source, "authorised")
        self.assertEqual(item.stake, 5.0)

    def test_signed_recommendation_requires_current_approval(self):
        from unittest.mock import patch
        from app.services.recommendation_signing_service import sign_recommendation

        with patch.dict(
            "os.environ",
            {"DARTSEDGE_RECOMMENDATION_SIGNING_KEY": "test-key-" * 8},
        ):
            token = sign_recommendation(
                fixture_id=self.fixture.id,
                market="Match Winner",
                selection="Slip Alpha",
                odds=2.1,
                effective_stake=5.0,
            )

            self.assertIsNotNone(token)

            current_row = {
                "fixture_id": self.fixture.id,
                "market": "Match Winner",
                "selection": "Slip Alpha",
                "bookmaker": "Paddy Power",
                "market_odds": 2.1,
                "effective_stake": 0.0,
                "decision_engine": None,
            }

            with patch(
                "app.services.value_board_service.build_value_board",
                return_value=[current_row],
            ):
                response = self.client.post(
                    "/bet-slip/add",
                    data={
                        "fixture_id": self.fixture.id,
                        "market": "Match Winner",
                        "selection": "Slip Alpha",
                        "bookmaker": "Paddy Power",
                        "odds": 2.1,
                        "stake": 5.0,
                        "recommendation_token": token,
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)

        item = self.db.query(BetSlipItem).filter(
            BetSlipItem.fixture_id == self.fixture.id
        ).one()

        self.assertEqual(item.stake_source, "unverified")

    def test_browser_supplied_stake_is_not_automatically_authorised(self):
        item, _ = add_bet_slip_item(
            self.db,
            fixture_id=self.fixture.id,
            market="Match Winner",
            selection="Slip Alpha",
            bookmaker="Paddy Power",
            odds=2.0,
            stake=20.0,
            model_probability=65.0,
            expected_value=10.0,
            kelly_stake=5.0,
            strategy_name="Active Strategy",
        )

        self.assertEqual(item.stake, 20.0)
        self.assertEqual(item.stake_source, "unverified")
