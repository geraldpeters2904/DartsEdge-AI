import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.prediction import Prediction
from app.models.paper_trade import PaperTrade


class PaperTradesUITests(unittest.TestCase):

    def test_template_exposes_decision_context(self):
        with open(
            "app/templates/paper_trades.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn("<th>Model %</th>", text)
        self.assertIn("<th>EV</th>", text)
        self.assertIn("<th>Kelly Reference</th>", text)
        self.assertIn("<th>Trade Stake</th>", text)
        self.assertIn("<th>Strategy</th>", text)

        self.assertIn("trade.model_probability", text)
        self.assertIn("trade.expected_value", text)
        self.assertIn("trade.suggested_stake", text)
        self.assertIn("trade.strategy_name", text)

    def test_template_exposes_fixture_context(self):
        with open(
            "app/templates/paper_trades.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn("<th>Fixture</th>", text)
        self.assertIn(
            "predictions_by_id.get(trade.prediction_id)",
            text,
        )
        self.assertIn("prediction.player_a", text)
        self.assertIn("prediction.player_b", text)
        self.assertIn("{% if prediction %}", text)
        self.assertIn("—", text)

    def test_historical_snapshot_values_have_fallback(self):
        with open(
            "app/templates/paper_trades.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn(
            "{% if trade.model_probability is not none %}",
            text,
        )
        self.assertIn(
            "{% if trade.expected_value is not none %}",
            text,
        )
        self.assertIn(
            "{% if trade.suggested_stake is not none %}",
            text,
        )
        self.assertIn(
            "{% if trade.strategy_name %}",
            text,
        )
        self.assertIn("—", text)

    def test_route_still_renders_with_historical_trades(self):
        db = SessionLocal()
        prediction = None
        trade = None

        try:
            prediction = Prediction(
                player_a="Historical Test Alpha",
                player_b="Historical Test Beta",
                predicted_winner="Historical Test Alpha",
                win_prob_a=60.0,
                win_prob_b=40.0,
            )
            db.add(prediction)
            db.flush()

            trade = PaperTrade(
                prediction_id=prediction.id,
                market="Match Winner",
                selection="Historical Test Alpha",
                bookmaker="Test Bookmaker",
                odds=2.0,
                stake=5.0,
                model_probability=60.0,
                expected_value=20.0,
                suggested_stake=7.5,
                strategy_name="test-strategy",
            )
            db.add(trade)
            db.commit()

            response = TestClient(app).get("/paper-trades")

            self.assertEqual(response.status_code, 200)
            self.assertIn("Paper Trades", response.text)
            self.assertIn("Model %", response.text)
            self.assertIn("Kelly Reference", response.text)
            self.assertIn("Strategy", response.text)
        finally:
            db.rollback()
            if trade is not None and trade.id is not None:
                db.query(PaperTrade).filter(
                    PaperTrade.id == trade.id
                ).delete()
            if prediction is not None and prediction.id is not None:
                db.query(Prediction).filter(
                    Prediction.id == prediction.id
                ).delete()
            db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
