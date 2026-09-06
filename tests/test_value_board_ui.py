import unittest

from fastapi.testclient import TestClient

from app.main import app


class ValueBoardUITests(unittest.TestCase):

    def test_template_exposes_live_value_fields(self):
        with open(
            "app/templates/value_board.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn("Bookmaker", text)
        self.assertIn("EV", text)
        self.assertIn("Status", text)
        self.assertIn('row.action == "Consider"', text)
        self.assertIn("🟢 Consider", text)
        self.assertIn('action="/bet-slip/add"', text)
        self.assertIn('name="fixture_id"', text)
        self.assertIn('name="selection"', text)
        self.assertIn('name="market"', text)
        self.assertIn('value="{{ row.market }}"', text)
        self.assertIn('name="odds"', text)
        self.assertIn('name="model_probability"', text)
        self.assertIn('name="expected_value"', text)
        self.assertIn("Add to Bet Slip", text)

    def test_route_still_renders(self):
        response = TestClient(app).get("/value-board")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Daily Value Board", response.text)


if __name__ == "__main__":
    unittest.main()
