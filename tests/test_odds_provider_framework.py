import json
import os
import tempfile
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.providers.remote_odds_json import RemoteJsonOddsProvider
from app.services.odds_provider_service import OddsProviderService


class OddsProviderFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        event_date = (date.today() + timedelta(days=1)).isoformat()
        json.dump({"odds": [
            {
                "external_id": "o1",
                "date": event_date,
                "tournament": "MODUS",
                "player_a": "Alpha",
                "player_b": "Beta",
                "bookmaker": "Example",
                "market": "Match Winner",
                "selection": "Alpha",
                "decimal_odds": 1.91,
                "captured_at": "2026-07-28T08:00:00Z"
            }
        ]}, self.temp)
        self.temp.close()

    def tearDown(self):
        os.unlink(self.temp.name)

    def test_remote_provider_parses_decimal_odds(self):
        provider = RemoteJsonOddsProvider(feed_url=f"file://{self.temp.name}")
        records = list(provider.fetch_odds(date.today(), date.today() + timedelta(days=7)))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].selection, "Alpha")
        self.assertAlmostEqual(records[0].decimal_odds, 1.91)

    def test_invalid_odds_are_rejected(self):
        bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump({"odds": [{
            "date": date.today().isoformat(), "player_a": "A", "player_b": "B",
            "bookmaker": "Example", "market": "Match Winner", "selection": "A", "decimal_odds": 1.0
        }]}, bad)
        bad.close()
        try:
            provider = RemoteJsonOddsProvider(feed_url=f"file://{bad.name}")
            with self.assertRaises(ValueError):
                list(provider.fetch_odds(date.today(), date.today()))
        finally:
            os.unlink(bad.name)

    def test_service_registers_manual_and_remote_providers(self):
        service = OddsProviderService()
        statuses = service.provider_status()
        self.assertEqual([row["id"] for row in statuses], ["manual-odds", "remote-odds-json"])
        self.assertEqual(statuses[0]["status"], "healthy")

    def test_remote_provider_disabled_without_url(self):
        provider = RemoteJsonOddsProvider(feed_url="")
        self.assertEqual(provider.health().status, "disabled")
        self.assertEqual(list(provider.fetch_odds(date.today(), date.today())), [])

    def test_odds_provider_routes_render(self):
        client = TestClient(app)
        page = client.get("/odds-providers")
        api = client.get("/api/odds-providers")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Odds Providers", page.text)
        self.assertEqual(api.status_code, 200)
        self.assertEqual(api.json()["registered"], 2)


if __name__ == "__main__":
    unittest.main()
