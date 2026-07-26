import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.strategy_profile import StrategyProfile
from app.services.decision_engine_service import decide
from app.services.strategy_service import seed_default_strategies, strategy_rules, update_strategy


class DecisionEngineTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        seed_default_strategies(self.db)

    def tearDown(self):
        self.db.close()

    def _decision(self, **overrides):
        values = dict(
            official_decision="Consider", official_stake=20.0, model_probability=70,
            confidence_percent=80, expected_value_percent=12, edge_percent=10,
            decimal_odds=2.0, bankroll=1000, market="match_winner",
            competition="modus", sample_size=50, portfolio_exposure_percent=2,
        )
        values.update(overrides)
        return decide(self.db, **values)

    def test_shadow_mode_preserves_official_decision(self):
        result = self._decision()
        self.assertFalse(result.enforced)
        self.assertEqual(result.effective_decision, "Consider")
        self.assertEqual(result.effective_stake, 20.0)

    def test_active_mode_accepts_qualifying_opportunity(self):
        active = self.db.query(StrategyProfile).filter_by(is_active=True).first()
        rules = strategy_rules(active); rules["enforcement_mode"] = "active"
        update_strategy(self.db, active.id, name=active.name, description=active.description, rules=rules)
        result = self._decision()
        self.assertTrue(result.enforced)
        self.assertEqual(result.effective_decision, "Accept")
        self.assertGreater(result.effective_stake, 0)

    def test_active_mode_rejects_blocked_opportunity(self):
        active = self.db.query(StrategyProfile).filter_by(is_active=True).first()
        rules = strategy_rules(active); rules["enforcement_mode"] = "active"
        update_strategy(self.db, active.id, name=active.name, description=active.description, rules=rules)
        result = self._decision(expected_value_percent=-5, edge_percent=-3)
        self.assertEqual(result.effective_decision, "Reject")
        self.assertEqual(result.effective_stake, 0)

    def test_paper_mode_never_returns_live_accept(self):
        paper = self.db.query(StrategyProfile).filter_by(name="Paper Trading").first()
        rules = strategy_rules(paper); rules["enforcement_mode"] = "active"
        replacement = update_strategy(self.db, paper.id, name=paper.name, description=paper.description, rules=rules)
        self.db.query(StrategyProfile).update({StrategyProfile.is_active: False})
        replacement.is_active = True; self.db.commit()
        result = self._decision()
        self.assertEqual(result.effective_decision, "Paper only")

    def test_strategy_stake_respects_strategy_cap(self):
        result = self._decision(official_stake=1000)
        self.assertLessEqual(result.strategy_stake, 30.0)


if __name__ == "__main__":
    unittest.main()
