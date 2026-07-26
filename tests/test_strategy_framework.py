import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models.strategy_profile import StrategyProfile
from app.services.strategy_service import activate_strategy, get_active_strategy, list_strategies, validate_rules


class StrategyFrameworkTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_default_strategies_are_seeded(self):
        db = self.Session()
        try:
            strategies = list(list_strategies(db))
            self.assertEqual(len(strategies), 5)
            self.assertEqual(get_active_strategy(db).name, "Default")
        finally:
            db.close()

    def test_activation_keeps_single_active_strategy(self):
        db = self.Session()
        try:
            strategies = list(list_strategies(db))
            target = next(item for item in strategies if item.name == "Conservative")
            activate_strategy(db, target.id)
            self.assertEqual(db.query(StrategyProfile).filter(StrategyProfile.is_active.is_(True)).count(), 1)
            self.assertEqual(get_active_strategy(db).name, "Conservative")
        finally:
            db.close()

    def test_rules_validation_rejects_invalid_mode(self):
        with self.assertRaises(ValueError):
            validate_rules({"mode": "unknown", "decision_rules_enabled": False})

    def test_strategy_page_route(self):
        response = TestClient(app).get("/strategies")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Strategy Framework", response.text)
        self.assertIn("Existing EV", response.text)

    def test_strategy_api_route(self):
        response = TestClient(app).get("/api/strategies")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["registered"], 5)
        self.assertEqual(payload["active"]["name"], "Default")


if __name__ == "__main__":
    unittest.main()
