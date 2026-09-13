from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.services.modus_stale_scope_grouping_service import (
    group_stale_modus_fixtures_by_scope,
)


class ModusStaleScopeGroupingTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def _add_fixture(
        self,
        fixture_id: int,
        *,
        series_id: int,
        week_id: int,
        group: str,
        player_a: str,
        player_b: str,
    ):
        match = Match(
            id=fixture_id,
            date=date(2026, 9, 7),
            tournament="MODUS Super Series",
            stage=group,
            status="scheduled",
            player_a=player_a,
            player_b=player_b,
        )
        self.db.add(match)
        self.db.flush()

        batch = HistoricalImportBatch(
            batch_uuid=f"batch-{fixture_id}",
            filename=(
                f"modus-series-{series_id}-"
                f"week-{week_id}-{group}.html"
            ),
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
        )
        self.db.add(batch)
        self.db.flush()

        self.db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="match",
                internal_id=fixture_id,
                external_id=f"modus-match-{74000000 + fixture_id}",
                action="created",
                created_by_batch=True,
            )
        )

    def test_groups_ordered_stale_fixtures_by_scope(self):
        self._add_fixture(
            100,
            series_id=26,
            week_id=196,
            group="Group A",
            player_a="Alpha",
            player_b="Bravo",
        )
        self._add_fixture(
            101,
            series_id=26,
            week_id=196,
            group="Group A",
            player_a="Charlie",
            player_b="Delta",
        )
        self._add_fixture(
            102,
            series_id=26,
            week_id=196,
            group="Group B",
            player_a="Echo",
            player_b="Foxtrot",
        )
        self.db.commit()

        groups = group_stale_modus_fixtures_by_scope(
            self.db,
            today=date(2026, 9, 8),
        )

        self.assertEqual(len(groups), 2)

        first = groups[0]
        self.assertEqual(first.scope.series_id, 26)
        self.assertEqual(first.scope.week_id, 196)
        self.assertEqual(first.scope.group, "Group A")
        self.assertEqual(
            tuple(item.fixture_id for item in first.fixtures),
            (100, 101),
        )

        second = groups[1]
        self.assertEqual(second.scope.group, "Group B")
        self.assertEqual(
            tuple(item.fixture_id for item in second.fixtures),
            (102,),
        )


if __name__ == "__main__":
    unittest.main()
