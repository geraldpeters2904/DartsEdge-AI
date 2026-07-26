import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.services.strategy_service import (
    evaluate_strategy,
    get_active_strategy,
    list_strategies,
    strategy_rules,
    validate_rules,
)


class StrategyRulesTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_seeded_profiles_have_complete_validated_rules(self):
        db = self.Session()
        try:
            profiles = list(list_strategies(db))
            self.assertEqual(len(profiles), 5)
            for profile in profiles:
                rules = strategy_rules(profile)
                self.assertTrue(rules["decision_rules_enabled"])
                self.assertEqual(rules["enforcement_mode"], "shadow")
                self.assertGreater(profile.version, 1)
        finally:
            db.close()

    def test_validation_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            validate_rules({"kelly_fraction": 1.5})
        with self.assertRaises(ValueError):
            validate_rules({"maximum_decimal_odds": 1.0})
        with self.assertRaises(ValueError):
            validate_rules({"allowed_markets": [""]})

    def test_conservative_filters_low_confidence_signal(self):
        db = self.Session()
        try:
            conservative = next(item for item in list_strategies(db) if item.name == "Conservative")
            decision = evaluate_strategy(
                conservative,
                model_probability=70,
                confidence_percent=65,
                expected_value_percent=10,
                edge_percent=9,
                decimal_odds=2.1,
                bankroll=5000,
                raw_kelly_stake=100,
                sample_size=30,
            )
            self.assertFalse(decision.qualifies)
            self.assertTrue(any("Confidence" in blocker for blocker in decision.blockers))
            self.assertEqual(decision.suggested_stake, 0)
        finally:
            db.close()

    def test_value_hunter_qualifies_and_caps_stake(self):
        db = self.Session()
        try:
            value_hunter = next(item for item in list_strategies(db) if item.name == "Value Hunter")
            decision = evaluate_strategy(
                value_hunter,
                model_probability=68,
                confidence_percent=75,
                expected_value_percent=12,
                edge_percent=8,
                decimal_odds=2.2,
                bankroll=1000,
                raw_kelly_stake=100,
                sample_size=50,
                portfolio_exposure_percent=5,
            )
            self.assertTrue(decision.qualifies)
            self.assertEqual(decision.suggested_stake, 30.0)
        finally:
            db.close()

    def test_strategy_page_and_api_expose_rules(self):
        client = TestClient(app)
        page = client.get("/strategies")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Strategy Rules", page.text)
        self.assertIn("Shadow evaluation", page.text)
        payload = client.get("/api/strategies").json()
        self.assertIn("rules", payload["active"])
        self.assertEqual(payload["active"]["enforcement_mode"], "shadow")


if __name__ == "__main__":
    unittest.main()
