import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services.prediction_audit_service import create_prediction_audit
from app.services.shadow_comparison_service import build_shadow_comparison, record_outcome


class ShadowComparisonTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def result(self, p=0.7, a_rating=80, b_rating=60):
        return {"player_a":"Alpha","player_b":"Bravo","win_prob_a":p,"recommendation":{"selection":"Alpha" if p>=.5 else "Bravo"},"explainability":{"selection":"Alpha","prediction_confidence":"High","explanation_confidence":{"label":"High"},"profile":{"name":"Default","version":1},"selection_intelligence_rating":a_rating,"opponent_intelligence_rating":b_rating}}

    def test_unsettled_records_do_not_count(self):
        create_prediction_audit(self.db, self.result())
        data = build_shadow_comparison(self.db)
        self.assertEqual(data["settled_count"], 0)

    def test_records_append_only_outcome(self):
        audit = create_prediction_audit(self.db, self.result())
        event = record_outcome(self.db, audit.audit_uuid, "Alpha")
        self.assertEqual(event.actual_winner, "Alpha")
        self.assertEqual(audit.official_selection, "Alpha")

    def test_rejects_unknown_winner(self):
        audit = create_prediction_audit(self.db, self.result())
        with self.assertRaises(ValueError):
            record_outcome(self.db, audit.audit_uuid, "Charlie")

    def test_computes_accuracy_and_brier(self):
        audit = create_prediction_audit(self.db, self.result())
        record_outcome(self.db, audit.audit_uuid, "Alpha")
        data = build_shadow_comparison(self.db)
        self.assertEqual(data["legacy"].accuracy, 1.0)
        self.assertIsNotNone(data["intelligence"].brier)

    def test_latest_outcome_event_wins(self):
        audit = create_prediction_audit(self.db, self.result())
        record_outcome(self.db, audit.audit_uuid, "Bravo")
        record_outcome(self.db, audit.audit_uuid, "Alpha", source="correction")
        data = build_shadow_comparison(self.db)
        self.assertEqual(data["rows"][0]["actual_winner"], "Alpha")


if __name__ == "__main__":
    unittest.main()
