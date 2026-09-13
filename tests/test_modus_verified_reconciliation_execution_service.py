from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.services.modus_verified_reconciliation_execution_service import (
    execute_verified_modus_reconciliation,
)


class SuccessfulWorkflow:
    def __init__(self):
        self.calls = []

    def run(self, db, candidate):
        self.calls.append(candidate)
        return "completed"


class FailingWorkflow:
    def run(self, db, candidate):
        raise RuntimeError("detail page failed")


class ModusVerifiedReconciliationExecutionTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

        self.match = Match(
            id=100,
            date=date(2026, 9, 7),
            tournament="MODUS Super Series",
            stage="Group A",
            status="scheduled",
            player_a="Alpha",
            player_b="Bravo",
        )
        self.db.add(self.match)
        self.db.flush()

        self.db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-74325910",
                internal_id=100,
                competition_code="MODUS",
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_replaces_mapping_and_runs_enrichment(self):
        workflow = SuccessfulWorkflow()

        result = execute_verified_modus_reconciliation(
            self.db,
            fixture_id=100,
            real_match_id=19695,
            workflow_service=workflow,
        )

        self.db.commit()

        self.assertEqual(result, "completed")
        self.assertEqual(len(workflow.calls), 1)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=100,
            )
            .one()
        )

        self.assertEqual(
            mapping.external_id,
            "modus-match-19695",
        )

    def test_enrichment_failure_rolls_mapping_back(self):
        with self.assertRaises(RuntimeError):
            execute_verified_modus_reconciliation(
                self.db,
                fixture_id=100,
                real_match_id=19695,
                workflow_service=FailingWorkflow(),
            )

        self.db.rollback()

        mappings = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=100,
            )
            .all()
        )

        self.assertEqual(len(mappings), 1)
        self.assertEqual(
            mappings[0].external_id,
            "modus-match-74325910",
        )


if __name__ == "__main__":
    unittest.main()
