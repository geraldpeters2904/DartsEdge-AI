import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.match import Match
from app.services.prediction_audit_service import (
    create_prediction_context_audit,
)
from app.services.prediction_settlement_service import (
    settle_completed_prediction_audits,
)
from app.services.shadow_comparison_service import latest_outcomes


class PredictionContextAuditSettlementTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def context(self, match_id=1):
        return SimpleNamespace(
            match_id=match_id,
            player_a_name="Alpha",
            player_b_name="Bravo",
            model_name="transparent-v3.3",
            model_version="transparent-v3.3",
            player_a_probability=61.2,
            player_b_probability=38.8,
            predicted_winner="Alpha",
            model_confidence=78.0,
            model_score=0.151,
            player_a_history_matches=40,
            player_b_history_matches=35,
            explanations=("Alpha scores better.",),
            contributions=(
                {
                    "feature": "scoring_power",
                    "weighted_score": 0.02,
                },
            ),
        )

    def add_match(
        self,
        match_id=1,
        *,
        status="scheduled",
        winner=None,
    ):
        row = Match(
            id=match_id,
            tournament="MODUS",
            stage="Group A",
            status=status,
            player_a="Alpha",
            player_b="Bravo",
            winner=winner,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_context_audit_uses_match_id(self):
        self.add_match()

        row = create_prediction_context_audit(
            self.db,
            self.context(),
            tournament="MODUS",
        )

        self.assertEqual(row.prediction_id, 1)
        self.assertEqual(row.model_version, "transparent-v3.3")
        self.assertEqual(row.intelligence_probability_a, 0.612)
        self.assertFalse(row.shadow_mode)

    def test_completed_match_settles_audit(self):
        self.add_match(
            status="completed",
            winner="Alpha",
        )

        audit = create_prediction_context_audit(
            self.db,
            self.context(),
        )

        report = settle_completed_prediction_audits(
            self.db
        )

        outcomes = latest_outcomes(
            self.db
        )

        self.assertEqual(report.settled, 1)
        self.assertEqual(
            outcomes[audit.id].actual_winner,
            "Alpha",
        )

    def test_settlement_is_idempotent(self):
        self.add_match(
            status="completed",
            winner="Bravo",
        )

        create_prediction_context_audit(
            self.db,
            self.context(),
        )

        first = settle_completed_prediction_audits(
            self.db
        )

        second = settle_completed_prediction_audits(
            self.db
        )

        self.assertEqual(first.settled, 1)
        self.assertEqual(second.settled, 0)
        self.assertEqual(second.already_settled, 1)

    def test_scheduled_match_is_not_settled(self):
        self.add_match(
            status="scheduled",
        )

        create_prediction_context_audit(
            self.db,
            self.context(),
        )

        report = settle_completed_prediction_audits(
            self.db
        )

        self.assertEqual(report.settled, 0)
        self.assertEqual(
            len(latest_outcomes(self.db)),
            0,
        )

    def test_invalid_result_is_skipped(self):
        self.add_match(
            status="completed",
            winner="Charlie",
        )

        create_prediction_context_audit(
            self.db,
            self.context(),
        )

        report = settle_completed_prediction_audits(
            self.db
        )

        self.assertEqual(report.settled, 0)
        self.assertEqual(report.invalid_match_result, 1)


if __name__ == "__main__":
    unittest.main()
