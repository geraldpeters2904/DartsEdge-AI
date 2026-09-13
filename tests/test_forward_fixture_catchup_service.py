import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.canonical_data import ProviderEntityMapping
from app.services.forward_fixture_catchup_service import (
    stale_scheduled_modus_fixtures,
    run_forward_fixture_catchup,
)


class ForwardFixtureCatchupTests(
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

    def test_stale_modus_fixture_is_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=1,
                date=date(
                    2026,
                    7,
                    15,
                ),
                tournament="MODUS",
                player_a="Lewis Pride",
                player_b="Devon Petersen",
                status="scheduled",
            )
        )

        self.db.commit()

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0].fixture_id,
            1,
        )

    def test_future_fixture_not_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=2,
                date=date(
                    2026,
                    8,
                    10,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            rows,
            (),
        )


    def test_provisional_mapping_alone_does_not_trigger_enrichment(
        self,
    ):
        self.db.add(
            Match(
                id=10,
                date=date(2026, 7, 15),
                tournament="MODUS Super Series",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )
        self.db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-74298014",
                internal_id=10,
                competition_code="MODUS",
            )
        )
        self.db.commit()

        class FakeWorkflow:

            def run(self, *args, **kwargs):
                raise AssertionError(
                    "A provisional fixture mapping must not "
                    "be treated as a completed MODUS match."
                )

        report = run_forward_fixture_catchup(
            self.db,
            today=date(2026, 8, 9),
            workflow_service=FakeWorkflow(),
        )

        self.assertEqual(report.candidates, 1)
        self.assertEqual(report.attempted, 0)
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.failed, 0)
        self.assertEqual(report.unchanged, 1)


    def test_unmapped_stale_fixture_is_not_enriched(

        self,

    ):

        self.db.add(

            Match(

                id=11,

                date=date(2026, 7, 15),

                tournament="MODUS Super Series",

                player_a="Charlie",

                player_b="Delta",

                status="scheduled",

            )

        )

        self.db.commit()

        class FakeWorkflow:

            def run(self, *args, **kwargs):

                raise AssertionError(

                    "Legacy orphan must not enter enrichment."

                )

        report = run_forward_fixture_catchup(

            self.db,

            today=date(2026, 8, 9),

            workflow_service=FakeWorkflow(),

        )

        self.assertEqual(report.candidates, 1)

        self.assertEqual(report.attempted, 0)

        self.assertEqual(report.completed, 0)

        self.assertEqual(report.unchanged, 1)

        self.assertEqual(report.failed, 0)


    def test_non_modus_fixture_not_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=3,
                date=date(
                    2026,
                    7,
                    1,
                ),
                tournament="PDC",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            rows,
            (),
        )


if __name__ == "__main__":
    unittest.main()


def test_scoped_stale_fixture_uses_sequence_reconciliation():
    import uuid
    from types import SimpleNamespace

    from app.models.historical_import import (
        HistoricalImportBatch,
        HistoricalImportItem,
    )

    db = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=db)
    Session = sessionmaker(bind=db)
    session = Session()

    try:
        match = Match(
            id=20,
            date=date(2026, 9, 10),
            tournament="MODUS Super Series",
            stage="Group B",
            player_a="Alpha",
            player_b="Bravo",
            status="scheduled",
        )
        session.add(match)
        session.flush()

        session.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-74325020",
                internal_id=20,
                competition_code="MODUS",
            )
        )

        batch = HistoricalImportBatch(
            batch_uuid=str(uuid.uuid4()),
            filename=(
                "modus-series-26-week-196-"
                "Group B.html"
            ),
            provider="modus-official",
            competition_code="MODUS",
            received_rows=1,
            status="imported",
        )
        session.add(batch)
        session.flush()

        session.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="match",
                internal_id=20,
                external_id="modus-match-74325020",
                action="created",
                created_by_batch=True,
            )
        )

        session.commit()

        class FakeFetcher:

            def fetch(self, scope):
                return (
                    SimpleNamespace(
                        match_id=19743,
                        match_number=1,
                        player_a_name="Bravo",
                        player_b_name="Alpha",
                    ),
                )

            def close(self):
                pass

        class FakeWorkflow:

            def __init__(self):
                self.calls = []

            def run(self, db, candidate):
                self.calls.append(candidate)
                return "completed"

        workflow = FakeWorkflow()

        report = run_forward_fixture_catchup(
            session,
            today=date(2026, 9, 12),
            workflow_service=workflow,
            completed_scope_fetcher=FakeFetcher(),
        )

        assert report.candidates == 1
        assert report.attempted == 1
        assert report.completed == 1
        assert report.failed == 0
        assert report.unchanged == 0

        assert len(workflow.calls) == 1
        assert (
            workflow.calls[0].resolved_modus_match_id
            == 19743
        )

        mapping = (
            session.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=20,
            )
            .one()
        )

        assert mapping.external_id == "modus-match-19743"

    finally:
        session.close()
