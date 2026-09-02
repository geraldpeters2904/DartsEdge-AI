import unittest

from fastapi.testclient import TestClient

from app.main import app


class PaperTradesUITests(unittest.TestCase):

    def test_template_exposes_decision_context(self):
        with open(
            "app/templates/paper_trades.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn("<th>Model %</th>", text)
        self.assertIn("<th>EV</th>", text)
        self.assertIn("<th>Suggested Stake</th>", text)
        self.assertIn("<th>Stake</th>", text)
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
        response = TestClient(app).get("/paper-trades")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Paper Trades", response.text)
        self.assertIn("Model %", response.text)
        self.assertIn("Suggested Stake", response.text)
        self.assertIn("Strategy", response.text)


if __name__ == "__main__":
    unittest.main()
