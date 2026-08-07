import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.match import Match
from app.models.prediction_audit import PredictionAudit
from app.services.prediction_audit_service import (
    get_or_create_prediction_context_audit,
)


class PredictionLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(
            Match(
                id=100,
                tournament="MODUS",
                stage="Group A",
                status="scheduled",
                player_a="Alpha",
                player_b="Bravo",
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def context(self):
        return SimpleNamespace(
            match_id=100,
            player_a_name="Alpha",
            player_b_name="Bravo",
            model_name="transparent-v3.3",
            model_version="transparent-v3.3",
            player_a_probability=61.2,
            player_b_probability=38.8,
            predicted_winner="Alpha",
            model_confidence=78.0,
            model_score=0.15,
            player_a_history_matches=40,
            player_b_history_matches=35,
            explanations=("Alpha scores better.",),
            contributions=(),
        )

    def test_get_or_create_is_idempotent(self):
        first, created_first = get_or_create_prediction_context_audit(
            self.db,
            self.context(),
            tournament="MODUS",
        )

        second, created_second = get_or_create_prediction_context_audit(
            self.db,
            self.context(),
            tournament="MODUS",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(
            self.db.query(PredictionAudit).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
