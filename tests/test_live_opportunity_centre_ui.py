import unittest

from fastapi.testclient import TestClient

from app.main import app


class LiveOpportunityCentreUITests(unittest.TestCase):

    def test_template_exposes_bet_slip_action(self):
        with open(
            "app/templates/live_opportunity_centre.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn('action="/bet-slip/add"', text)
        self.assertIn('name="fixture_id"', text)
        self.assertIn('name="market"', text)
        self.assertIn('name="selection"', text)
        self.assertIn('name="bookmaker"', text)
        self.assertIn('name="odds"', text)
        self.assertIn('name="stake"', text)
        self.assertIn('name="model_probability"', text)
        self.assertIn('name="expected_value"', text)
        self.assertIn('name="kelly_stake"', text)
        self.assertIn('name="strategy_name"', text)
        self.assertIn(
            "{{ active_strategy.name }} v{{ active_strategy.version }}",
            text,
        )
        self.assertIn("Add to Bet Slip", text)

    def test_replay_action_remains_available(self):
        with open(
            "app/templates/live_opportunity_centre.html",
            encoding="utf-8",
        ) as handle:
            text = handle.read()

        self.assertIn(
            'href="/opportunities/{{ item.fixture_id }}/replay"',
            text,
        )
        self.assertIn("Replay", text)

    def test_route_still_renders(self):
        response = TestClient(app).get("/opportunities")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Live Opportunity Centre", response.text)


if __name__ == "__main__":
    unittest.main()
