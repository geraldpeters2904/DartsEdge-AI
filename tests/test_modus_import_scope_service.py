from __future__ import annotations

import unittest

from app.services.modus_import_scope_service import (
    parse_modus_import_scope,
)


class ModusImportScopeServiceTests(unittest.TestCase):

    def test_parses_group_a_scope(self):
        scope = parse_modus_import_scope(
            "modus-series-26-week-196-Group A.html"
        )

        self.assertIsNotNone(scope)
        self.assertEqual(scope.series_id, 26)
        self.assertEqual(scope.week_id, 196)
        self.assertEqual(scope.group, "Group A")

    def test_parses_final_scope(self):
        scope = parse_modus_import_scope(
            "modus-series-26-week-195-Final.html"
        )

        self.assertIsNotNone(scope)
        self.assertEqual(scope.series_id, 26)
        self.assertEqual(scope.week_id, 195)
        self.assertEqual(scope.group, "Final")

    def test_unrelated_filename_returns_none(self):
        self.assertIsNone(
            parse_modus_import_scope("fixtures.csv")
        )


if __name__ == "__main__":
    unittest.main()


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.services.modus_import_scope_service import (
    find_modus_import_scope_for_match,
)


class ModusImportScopeLookupTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_finds_scope_from_created_match_item(self):
        batch = HistoricalImportBatch(
            batch_uuid="batch-created",
            filename="modus-series-26-week-196-Group B.html",
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
                internal_id=123,
                external_id="modus-match-74300001",
                action="created",
                created_by_batch=True,
            )
        )
        self.db.commit()

        scope = find_modus_import_scope_for_match(
            self.db,
            123,
        )

        self.assertIsNotNone(scope)
        self.assertEqual(scope.series_id, 26)
        self.assertEqual(scope.week_id, 196)
        self.assertEqual(scope.group, "Group B")

    def test_finds_scope_from_later_fixture_item(self):
        batch = HistoricalImportBatch(
            batch_uuid="batch-duplicate",
            filename="modus-series-27-week-201-Final.html",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
        )
        self.db.add(batch)
        self.db.flush()

        self.db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="fixture",
                internal_id=456,
                external_id="modus-match-74400001",
                action="duplicate",
                created_by_batch=False,
            )
        )
        self.db.commit()

        scope = find_modus_import_scope_for_match(
            self.db,
            456,
        )

        self.assertIsNotNone(scope)
        self.assertEqual(scope.series_id, 27)
        self.assertEqual(scope.week_id, 201)
        self.assertEqual(scope.group, "Final")

    def test_ignores_unrelated_batch_filename(self):
        batch = HistoricalImportBatch(
            batch_uuid="batch-unrelated",
            filename="fixtures.csv",
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
                internal_id=789,
                external_id="modus-match-74500001",
                action="created",
                created_by_batch=True,
            )
        )
        self.db.commit()

        self.assertIsNone(
            find_modus_import_scope_for_match(
                self.db,
                789,
            )
        )


def test_lookup_skips_newer_unrelated_audit_batch():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    try:
        source_batch = HistoricalImportBatch(
            batch_uuid="source-batch",
            filename="modus-series-26-week-196-Group A.html",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
        )
        db.add(source_batch)
        db.flush()

        db.add(
            HistoricalImportItem(
                batch_id=source_batch.id,
                entity_type="match",
                internal_id=999,
                external_id="modus-match-74325910",
                action="created",
                created_by_batch=True,
            )
        )
        db.commit()

        audit_batch = HistoricalImportBatch(
            batch_uuid="audit-batch",
            filename="lifecycle-reconciliation",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
        )
        db.add(audit_batch)
        db.flush()

        db.add(
            HistoricalImportItem(
                batch_id=audit_batch.id,
                entity_type="fixture",
                internal_id=999,
                external_id="modus-match-74325910",
                action="updated",
                created_by_batch=False,
                detail="Lifecycle cancellation audit.",
            )
        )
        db.commit()

        scope = find_modus_import_scope_for_match(
            db,
            999,
        )

        assert scope is not None
        assert scope.series_id == 26
        assert scope.week_id == 196
        assert scope.group == "Group A"

    finally:
        db.close()
