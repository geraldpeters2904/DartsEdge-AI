import unittest
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.opportunity_snapshot import (
    OpportunitySnapshot,
)
from app.services.live_opportunity_centre_service import (
    _persist_if_changed,
)


class LiveOpportunityDecisionSafetyPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            bind=engine
        )

        Session = sessionmaker(
            bind=engine
        )

        self.db = Session()

        self.fixture = SimpleNamespace(
            id=100,
            date=date(2026, 8, 12),
            tournament="MODUS",
            player_a="Alpha",
            player_b="Bravo",
        )

        self.opportunity = {
            "selection": "Alpha",
            "probability": 67.0,
            "model_confidence": 75.0,
        }

        self.assessment = SimpleNamespace(
            expected_value_percent=5.0,
            edge_percent=3.0,
            recommended_stake=10.0,
        )

        self.price = SimpleNamespace(
            bookmaker="Book",
            decimal_odds=2.0,
        )

        self.decision = {
            "score": 80,
            "grade": "Excellent",
            "recommendation": "BET",
            "consensus_score": 80.0,
            "steam_direction": None,
            "steam_strength": None,
            "coordinated_move": False,
            "strategy_suggested_stake": 10.0,
        }

    def tearDown(self):
        self.db.close()

    def test_persists_decision_safety_snapshot(self):
        safety = {
            "state": "HIGH_CAUTION",
            "caution": True,
            "high_caution": True,
            "trust_score": 72.0,
            "sparse_consensus_risk_state": (
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            "explanation": (
                "High regime risk."
            ),
            "density": 5.921053,
        }

        written = _persist_if_changed(
            self.db,
            fixture=self.fixture,
            opportunity=self.opportunity,
            assessment=self.assessment,
            price=self.price,
            decision=self.decision,
            decision_safety=safety,
            lifecycle_state="NEW",
        )

        self.assertTrue(written)

        row = (
            self.db.query(OpportunitySnapshot)
            .one()
        )

        self.assertEqual(
            row.decision_safety_state,
            "HIGH_CAUTION",
        )

        self.assertEqual(
            row.sparse_consensus_risk_state,
            "HIGH_SPARSE_CONSENSUS_RISK",
        )

        self.assertAlmostEqual(
            row.sparse_consensus_density,
            5.921053,
            places=6,
        )

        self.assertEqual(
            row.decision_safety_explanation,
            "High regime risk.",
        )

    def test_safety_change_creates_new_snapshot(self):
        normal = {
            "state": "NORMAL",
            "sparse_consensus_risk_state": "NORMAL",
            "explanation": "Normal.",
            "density": 0.5,
        }

        high = {
            "state": "HIGH_CAUTION",
            "sparse_consensus_risk_state": (
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            "explanation": "High.",
            "density": 5.9,
        }

        first = _persist_if_changed(
            self.db,
            fixture=self.fixture,
            opportunity=self.opportunity,
            assessment=self.assessment,
            price=self.price,
            decision=self.decision,
            decision_safety=normal,
            lifecycle_state="NEW",
        )

        second = _persist_if_changed(
            self.db,
            fixture=self.fixture,
            opportunity=self.opportunity,
            assessment=self.assessment,
            price=self.price,
            decision=self.decision,
            decision_safety=high,
            lifecycle_state="NEW",
        )

        self.assertTrue(first)
        self.assertTrue(second)

        rows = (
            self.db.query(OpportunitySnapshot)
            .order_by(
                OpportunitySnapshot.id.asc()
            )
            .all()
        )

        self.assertEqual(
            len(rows),
            2,
        )

        self.assertEqual(
            rows[0].decision_safety_state,
            "NORMAL",
        )

        self.assertEqual(
            rows[1].decision_safety_state,
            "HIGH_CAUTION",
        )


if __name__ == "__main__":
    unittest.main()
