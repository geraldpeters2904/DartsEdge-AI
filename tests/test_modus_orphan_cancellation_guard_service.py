from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import (
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_orphan_cancellation_guard_service import (
    check_orphan_cancellation_eligibility,
)
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)


def _database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _group(fixture_id=17855):
    return StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=fixture_id,
                fixture_date=date(2026, 9, 19),
                player_a="Richie Howson",
                player_b="Keegan Brown",
                stage="Group B",
            ),
        ),
    )


def _add_candidate(
    db,
    *,
    fixture_id=17855,
    external_id="modus-match-74834978",
    status="scheduled",
    filename="modus-series-26-week-197-Group B.html",
    raw_status="scheduled",
    add_mapping=True,
):
    db.add(
        Match(
            id=fixture_id,
            date=date(2026, 9, 19),
            tournament="MODUS Super Series",
            stage="Group B",
            match_format="Best of 7",
            status=status,
            player_a="Richie Howson",
            player_b="Keegan Brown",
        )
    )

    batch = HistoricalImportBatch(
        batch_uuid=f"guard-batch-{fixture_id}",
        filename=filename,
        provider="modus-official",
        competition_code="MODUS",
        status="imported",
    )
    db.add(batch)
    db.flush()

    db.add(
        HistoricalImportItem(
            batch_id=batch.id,
            entity_type="fixture",
            internal_id=fixture_id,
            external_id=external_id,
            action="created",
            created_by_batch=True,
        )
    )

    if add_mapping:
        db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id=external_id,
                internal_id=fixture_id,
                competition_code="MODUS",
            )
        )

    payload = {
        "external_id": external_id,
        "status": raw_status,
    }
    payload_json = json.dumps(payload, sort_keys=True)

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


def test_scheduled_exact_scope_strict_mapping_without_completed_raw_is_eligible():
    db = _database()

    try:
        _add_candidate(db)

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert result.eligible
        assert result.fixture_id == 17855
        assert result.external_id == "modus-match-74834978"
    finally:
        db.close()


def test_completed_raw_observation_rejects_cancellation():
    db = _database()

    try:
        _add_candidate(
            db,
            raw_status="completed",
        )

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert "completed raw MODUS observation" in result.reason
    finally:
        db.close()


def test_missing_strict_mapping_rejects_legacy_orphan():
    db = _database()

    try:
        _add_candidate(
            db,
            add_mapping=False,
        )

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert result.external_id is None
    finally:
        db.close()


def test_wrong_scope_rejects_cancellation():
    db = _database()

    try:
        _add_candidate(
            db,
            filename="modus-series-26-week-196-Group B.html",
        )

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert "exact MODUS scope" in result.reason
    finally:
        db.close()


def test_non_scheduled_match_rejects_cancellation():
    db = _database()

    try:
        _add_candidate(
            db,
            status="completed",
        )

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert "no longer scheduled" in result.reason
    finally:
        db.close()


def test_no_raw_observation_rejects_cancellation():
    db = _database()

    try:
        _add_candidate(db)

        db.query(RawIngestionRecord).delete()
        db.commit()

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert "No raw MODUS observations" in result.reason
    finally:
        db.close()


def test_multiple_strict_mappings_reject_cancellation():
    db = _database()

    try:
        _add_candidate(db)

        db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-99999999",
                internal_id=17855,
                competition_code="MODUS",
            )
        )
        db.commit()

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert result.external_id is None
        assert "exactly one strict" in result.reason
    finally:
        db.close()


def test_malformed_raw_observation_rejects_cancellation():
    db = _database()

    try:
        _add_candidate(db)

        db.add(
            RawIngestionRecord(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-74834978",
                payload_json="{not-valid-json",
                checksum="malformed-test-record",
                retrieved_at=datetime(2026, 9, 19, 0, 6, 0),
                processed=True,
            )
        )
        db.commit()

        result = check_orphan_cancellation_eligibility(
            db,
            _group(),
            17855,
        )

        assert not result.eligible
        assert result.external_id == "modus-match-74834978"
        assert "cannot be parsed safely" in result.reason
    finally:
        db.close()
