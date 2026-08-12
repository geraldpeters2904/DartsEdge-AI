import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.opportunity_snapshot import (
    OpportunitySnapshot,
)
from app.services.decision_safety_outcome_evidence_service import (
    build_decision_safety_outcome_evidence,
)


class DecisionSafetyOutcomeEvidenceTests(
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

    def tearDown(self):
        self.db.close()

    def add_match(
        self,
        fixture_id,
        winner,
    ):
        self.db.add(
            Match(
                id=fixture_id,
                date=date(
                    2026,
                    8,
                    12,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="completed",
                winner=winner,
            )
        )

    def add_snapshot(
        self,
        fixture_id,
        *,
        state,
        selection="Alpha",
        odds=2.0,
        stake=10.0,
        ev=5.0,
        edge=3.0,
        captured_at=None,
    ):
        self.db.add(
            OpportunitySnapshot(
                fixture_id=fixture_id,
                fixture_date=date(
                    2026,
                    8,
                    12,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                selection=selection,
                market="match_winner",
                bookmaker="Book",
                decimal_odds=odds,
                model_probability=67.0,
                model_confidence=75.0,
                expected_value_percent=ev,
                edge_percent=edge,
                decision_score=80,
                decision_grade="Excellent",
                recommendation="BET",
                coordinated_move=False,
                lifecycle_state="NEW",
                suggested_stake=stake,
                decision_safety_state=state,
                sparse_consensus_risk_state=(
                    "NORMAL"
                ),
                captured_at=(
                    captured_at
                    or datetime.utcnow()
                ),
            )
        )

    def metric(self, evidence, state):
        return next(
            metric
            for metric in evidence.states
            if metric.state == state
        )

    def test_calculates_win_rate_and_roi(self):
        self.add_match(
            1,
            "Alpha",
        )
        self.add_snapshot(
            1,
            state="NORMAL",
            odds=2.0,
            stake=10.0,
        )

        self.add_match(
            2,
            "Bravo",
        )
        self.add_snapshot(
            2,
            state="NORMAL",
            odds=2.0,
            stake=10.0,
        )

        self.db.commit()

        evidence = (
            build_decision_safety_outcome_evidence(
                self.db
            )
        )

        normal = self.metric(
            evidence,
            "NORMAL",
        )

        self.assertEqual(
            normal.settled,
            2,
        )
        self.assertEqual(
            normal.wins,
            1,
        )
        self.assertEqual(
            normal.losses,
            1,
        )
        self.assertEqual(
            normal.win_rate_percent,
            50.0,
        )
        self.assertEqual(
            normal.total_staked,
            20.0,
        )
        self.assertEqual(
            normal.profit_loss,
            0.0,
        )
        self.assertEqual(
            normal.roi_percent,
            0.0,
        )

    def test_latest_snapshot_per_fixture_is_used(self):
        self.add_match(
            10,
            "Alpha",
        )

        now = datetime.utcnow()

        self.add_snapshot(
            10,
            state="NORMAL",
            captured_at=(
                now
                - timedelta(
                    minutes=5
                )
            ),
        )

        self.add_snapshot(
            10,
            state="HIGH_CAUTION",
            captured_at=now,
        )

        self.db.commit()

        evidence = (
            build_decision_safety_outcome_evidence(
                self.db
            )
        )

        normal = self.metric(
            evidence,
            "NORMAL",
        )

        high = self.metric(
            evidence,
            "HIGH_CAUTION",
        )

        self.assertEqual(
            normal.snapshots,
            0,
        )

        self.assertEqual(
            high.snapshots,
            1,
        )

        self.assertEqual(
            high.settled,
            1,
        )

        self.assertEqual(
            evidence.total_fixtures,
            1,
        )

    def test_unsettled_fixture_not_in_win_rate(self):
        self.db.add(
            Match(
                id=20,
                date=date(
                    2026,
                    8,
                    12,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.add_snapshot(
            20,
            state="CAUTION",
        )

        self.db.commit()

        evidence = (
            build_decision_safety_outcome_evidence(
                self.db
            )
        )

        caution = self.metric(
            evidence,
            "CAUTION",
        )

        self.assertEqual(
            caution.snapshots,
            1,
        )

        self.assertEqual(
            caution.settled,
            0,
        )

        self.assertIsNone(
            caution.win_rate_percent
        )

        self.assertIsNone(
            caution.roi_percent
        )

    def test_old_unknown_rows_are_supported(self):
        self.add_match(
            30,
            "Alpha",
        )

        self.add_snapshot(
            30,
            state="UNKNOWN",
        )

        self.db.commit()

        evidence = (
            build_decision_safety_outcome_evidence(
                self.db
            )
        )

        unknown = self.metric(
            evidence,
            "UNKNOWN",
        )

        self.assertEqual(
            unknown.snapshots,
            1,
        )

        self.assertEqual(
            unknown.wins,
            1,
        )


if __name__ == "__main__":
    unittest.main()
