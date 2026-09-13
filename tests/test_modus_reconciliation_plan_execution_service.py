from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.services.modus_reconciliation_plan_execution_service import (
    execute_modus_reconciliation_mappings,
)


class SelectiveWorkflow:
    def __init__(self, failing_fixture_id=None):
        self.failing_fixture_id = failing_fixture_id
        self.calls = []

    def run(self, db, candidate):
        self.calls.append(candidate.internal_match_id)

        if (
            candidate.internal_match_id
            == self.failing_fixture_id
        ):
            raise RuntimeError("detail page failed")

        return "completed"


class ModusReconciliationPlanExecutionTests(
    unittest.TestCase
):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

        for fixture_id, provisional_id in (
            (100, 74325001),
            (101, 74325002),
            (102, 74325003),
        ):
            self.db.add(
                Match(
                    id=fixture_id,
                    date=date(2026, 9, 7),
                    tournament="MODUS Super Series",
                    stage="Group A",
                    status="scheduled",
                    player_a=f"Player {fixture_id}A",
                    player_b=f"Player {fixture_id}B",
                )
            )
            self.db.flush()

            self.db.add(
                ProviderEntityMapping(
                    provider="modus-official",
                    entity_type="fixture",
                    external_id=(
                        f"modus-match-{provisional_id}"
                    ),
                    internal_id=fixture_id,
                    competition_code="MODUS",
                )
            )

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_failure_rolls_back_only_failed_fixture(self):
        workflow = SelectiveWorkflow(
            failing_fixture_id=101,
        )

        report = execute_modus_reconciliation_mappings(
            self.db,
            mappings=(
                (100, 19691),
                (101, 19693),
                (102, 19695),
            ),
            workflow_service=workflow,
        )

        self.assertEqual(report.attempted, 3)
        self.assertEqual(report.completed, 2)
        self.assertEqual(report.failed, 1)
        self.assertEqual(
            report.failed_fixture_ids,
            (101,),
        )

        mappings = {
            row.internal_id: row.external_id
            for row in (
                self.db.query(ProviderEntityMapping)
                .filter_by(
                    provider="modus-official",
                    entity_type="fixture",
                )
                .all()
            )
        }

        self.assertEqual(
            mappings[100],
            "modus-match-19691",
        )

        self.assertEqual(
            mappings[101],
            "modus-match-74325002",
        )

        self.assertEqual(
            mappings[102],
            "modus-match-19695",
        )

        self.assertEqual(
            workflow.calls,
            [100, 101, 102],
        )


if __name__ == "__main__":
    unittest.main()
