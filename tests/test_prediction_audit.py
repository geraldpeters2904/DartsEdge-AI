import json
import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.prediction_audit import PredictionAudit
from app.services.prediction_audit_service import audit_snapshot, audits_csv, create_prediction_audit, list_audits
from app.models.player import Player
from app.models.match import Match


class PredictionAuditTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def result(self, player_a="Alpha", player_b="Bravo"):
        return {
            "player_a": player_a, "player_b": player_b,
            "win_prob_a": 0.68, "win_prob_b": 0.32,
            "recommendation": {"selection": player_a},
            "confidence": {"score": 74},
            "explainability": {
                "selection": player_a, "prediction_confidence": "Medium",
                "explanation_confidence": {"label": "High"},
                "profile": {"name": "Default", "version": 1},
                "selection_intelligence_rating": 76.0,
                "opponent_intelligence_rating": 61.0,
                "summary": "Elo is the leading factor.",
            },
            "profile_a": {"elo": 1600}, "profile_b": {"elo": 1500},
        }

    def test_creates_uuid_and_snapshot(self):
        row = create_prediction_audit(self.db, self.result(), prediction_id=7)
        self.assertEqual(len(row.audit_uuid), 36)
        self.assertEqual(row.prediction_id, 7)
        self.assertEqual(audit_snapshot(row)["official"]["selection"], "Alpha")

    def test_append_only_creates_distinct_rows(self):
        first = create_prediction_audit(self.db, self.result())
        second = create_prediction_audit(self.db, self.result())
        self.assertNotEqual(first.audit_uuid, second.audit_uuid)
        self.assertEqual(self.db.query(PredictionAudit).count(), 2)

    def test_records_profile_and_model_versions(self):
        row = create_prediction_audit(self.db, self.result())
        self.assertEqual(row.profile_name, "Default")
        self.assertEqual(row.profile_version, 1)
        self.assertIn("shadow", row.model_version)

    def test_filters_by_player_and_profile(self):
        first = create_prediction_audit(self.db, self.result())
        second = create_prediction_audit(
            self.db,
            self.result("Charlie", "Delta"),
        )
        self.assertEqual(len(list_audits(self.db, player="Alpha")), 1)
        self.assertEqual(len(list_audits(self.db, profile="Default")), 2)

        created_dates = [
            first.created_at.date(),
            second.created_at.date(),
        ]
        self.assertEqual(
            len(
                list_audits(
                    self.db,
                    date_from=min(created_dates),
                )
            ),
            2,
        )

    def test_csv_export_has_stable_columns(self):
        row = create_prediction_audit(self.db, self.result())
        content = audits_csv([row])
        self.assertIn("audit_uuid,created_at,source", content)
        self.assertIn(row.audit_uuid, content)


if __name__ == "__main__":
    unittest.main()
