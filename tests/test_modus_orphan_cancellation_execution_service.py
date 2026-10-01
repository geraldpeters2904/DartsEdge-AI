from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import (
    DataProvenance,
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_orphan_cancellation_execution_service import (
    execute_derived_orphan_cancellation,
)
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)


def _database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _group():
    return StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=17855,
                fixture_date=date(2026, 9, 19),
                player_a="Richie Howson",
                player_b="Keegan Brown",
                stage="Group B",
            ),
        ),
    )


def _seed_eligible_candidate(db):
    external_id = "modus-match-74834978"

    db.add(
        Match(
            id=17855,
            date=date(2026, 9, 19),
            tournament="MODUS Super Series",
            stage="Group B",
            match_format="Best of 7",
            status="scheduled",
            player_a="Richie Howson",
            player_b="Keegan Brown",
        )
    )

    batch = HistoricalImportBatch(
        batch_uuid="original-import-batch",
        filename="modus-series-26-week-197-Group B.html",
        provider="modus-official",
        competition_code="MODUS",
        status="imported",
        received_rows=1,
    )
    db.add(batch)
    db.flush()

    db.add(
        HistoricalImportItem(
            batch_id=batch.id,
            entity_type="fixture",
            internal_id=17855,
            external_id=external_id,
            action="created",
            created_by_batch=True,
        )
    )

    db.add(
        ProviderEntityMapping(
            provider="modus-official",
            entity_type="fixture",
            external_id=external_id,
            internal_id=17855,
            competition_code="MODUS",
        )
    )

    payload_json = json.dumps(
        {
            "external_id": external_id,
            "status": "scheduled",
        },
        sort_keys=True,
    )

    db.add(
        RawIngestionRecord(
            provider="modus-official",
            entity_type="fixture",
            external_id=external_id,
            payload_json=payload_json,
            checksum=hashlib.sha256(
                payload_json.encode("utf-8")
            ).hexdigest(),
            retrieved_at=datetime(2026, 9, 19, 0, 5, 34),
            processed=True,
        )
    )

    db.commit()


def test_executor_cancels_eligible_orphan_with_derived_audit():
    db = _database()

    try:
        _seed_eligible_candidate(db)

        raw_count_before = db.query(RawIngestionRecord).count()

        result = execute_derived_orphan_cancellation(
            db,
            group=_group(),
            fixture_id=17855,
            structural_reason=(
                "Official completed cards form a complete balanced "
                "2-round-robin."
            ),
        )

        match = db.query(Match).filter(Match.id == 17855).one()
        assert match.status == "cancelled"

        assert result.fixture_id == 17855
        assert result.external_id == "modus-match-74834978"
        assert result.previous_status == "scheduled"
        assert result.status == "cancelled"

        mappings = (
            db.query(ProviderEntityMapping)
            .filter(
                ProviderEntityMapping.provider == "modus-official",
                ProviderEntityMapping.entity_type == "fixture",
                ProviderEntityMapping.internal_id == 17855,
            )
            .all()
        )
        assert len(mappings) == 1
        assert mappings[0].external_id == "modus-match-74834978"

        assert db.query(RawIngestionRecord).count() == raw_count_before

        provenance = (
            db.query(DataProvenance)
            .filter(
                DataProvenance.entity_type == "fixture",
                DataProvenance.internal_id == 17855,
                DataProvenance.field_name == "status",
                DataProvenance.provider == "modus-reconciliation",
            )
            .one()
        )
        assert provenance.external_id == "modus-match-74834978"
        assert provenance.confidence == "derived"

        audit_batch = (
            db.query(HistoricalImportBatch)
            .filter(
                HistoricalImportBatch.id == result.batch_id,
            )
            .one()
        )
        assert audit_batch.provider == "modus-reconciliation"
        assert audit_batch.status == "imported"
        assert audit_batch.received_rows == 1

        audit_item = (
            db.query(HistoricalImportItem)
            .filter(
                HistoricalImportItem.batch_id == result.batch_id,
                HistoricalImportItem.internal_id == 17855,
            )
            .one()
        )
        assert audit_item.action == "updated"
        assert not audit_item.created_by_batch

        detail = json.loads(audit_item.detail)
        assert detail["operation"] == "derived_orphan_cancellation"
        assert detail["confidence"] == "derived"
        assert detail["previous"]["status"] == "scheduled"
        assert detail["current"]["status"] == "cancelled"
        assert (
            detail["evidence"]["official_external_id"]
            == "modus-match-74834978"
        )
        assert detail["evidence"]["scope"] == {
            "series_id": 26,
            "week_id": 197,
            "group": "Group B",
        }
    finally:
        db.rollback()
        db.close()


def test_executor_refuses_candidate_with_completed_raw_observation():
    db = _database()

    try:
        _seed_eligible_candidate(db)

        record = db.query(RawIngestionRecord).one()
        payload_json = json.dumps(
            {
                "external_id": "modus-match-74834978",
                "status": "completed",
            },
            sort_keys=True,
        )
        record.payload_json = payload_json
        record.checksum = hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()
        db.commit()

        batch_count_before = db.query(HistoricalImportBatch).count()

        try:
            execute_derived_orphan_cancellation(
                db,
                group=_group(),
                fixture_id=17855,
                structural_reason="Test structural evidence.",
            )
            assert False, "Expected cancellation to be rejected."
        except ValueError as exc:
            assert "not eligible" in str(exc)

        match = db.query(Match).filter(Match.id == 17855).one()
        assert match.status == "scheduled"

        assert (
            db.query(HistoricalImportBatch).count()
            == batch_count_before
        )

        assert (
            db.query(DataProvenance)
            .filter(
                DataProvenance.internal_id == 17855,
                DataProvenance.provider == "modus-reconciliation",
            )
            .count()
            == 0
        )

        assert (
            db.query(HistoricalImportItem)
            .join(
                HistoricalImportBatch,
                HistoricalImportItem.batch_id
                == HistoricalImportBatch.id,
            )
            .filter(
                HistoricalImportBatch.provider
                == "modus-reconciliation",
            )
            .count()
            == 0
        )
    finally:
        db.rollback()
        db.close()


def test_executor_changes_are_fully_rollbackable_before_commit():
    db = _database()

    try:
        _seed_eligible_candidate(db)

        original_batch_count = db.query(HistoricalImportBatch).count()
        original_provenance_count = db.query(DataProvenance).count()

        execute_derived_orphan_cancellation(
            db,
            group=_group(),
            fixture_id=17855,
            structural_reason="Test structural evidence.",
        )

        assert (
            db.query(Match)
            .filter(Match.id == 17855)
            .one()
            .status
            == "cancelled"
        )

        db.rollback()

        assert (
            db.query(Match)
            .filter(Match.id == 17855)
            .one()
            .status
            == "scheduled"
        )

        assert (
            db.query(HistoricalImportBatch).count()
            == original_batch_count
        )

        assert (
            db.query(DataProvenance).count()
            == original_provenance_count
        )

        assert (
            db.query(HistoricalImportBatch)
            .filter(
                HistoricalImportBatch.provider
                == "modus-reconciliation",
            )
            .count()
            == 0
        )
    finally:
        db.rollback()
        db.close()
