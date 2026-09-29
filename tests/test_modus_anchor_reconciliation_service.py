from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.models.historical_import import HistoricalImportBatch, HistoricalImportItem

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)


def test_left_verified_anchor_resolves_only_immediate_next_fixture():
    group = StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=17830,
                fixture_date=date(2026, 9, 18),
                player_a="Richie Howson",
                player_b="Keegan Brown",
                stage="Group B",
            ),
            ScopedStaleFixture(
                fixture_id=17855,
                fixture_date=date(2026, 9, 19),
                player_a="Richie Howson",
                player_b="Keegan Brown",
                stage="Group B",
            ),
        ),
    )

    completed_cards = tuple(
        SimpleNamespace(
            match_id=match_id,
            match_number=match_number,
            player_a_name=player_a,
            player_b_name=player_b,
        )
        for match_id, match_number, player_a, player_b in (
            (19993, 11, "Richie Howson", "Steve Green"),
            (19995, 12, "Keegan Brown", "Henry Cooper"),
            (19997, 13, "Steve Green", "Chas Barstow"),
            (19999, 14, "Henry Cooper", "Richie Howson"),
            (20001, 15, "Chas Barstow", "Keegan Brown"),
            (20003, 16, "Steve Green", "Henry Cooper"),
            (20005, 17, "Chas Barstow", "Richie Howson"),
            (20007, 18, "Keegan Brown", "Steve Green"),
            (20009, 19, "Henry Cooper", "Chas Barstow"),
            (20011, 20, "Richie Howson", "Keegan Brown"),
        )
    )

    from app.services.modus_anchor_reconciliation_service import (
        VerifiedSequenceAnchor,
        build_anchor_aware_stale_reconciliation_plan,
    )

    plan = build_anchor_aware_stale_reconciliation_plan(
        group,
        completed_cards,
        anchors=(
            VerifiedSequenceAnchor(
                fixture_id=17829,
                real_match_id=20009,
            ),
        ),
    )

    assert plan.resolved
    assert plan.mappings == ((17830, 20011),)
    assert plan.unmatched_fixture_ids == (17855,)

def test_anchor_not_on_completed_card_is_rejected():
    group = StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=17830,
                fixture_date=date(2026, 9, 18),
                player_a="Richie Howson",
                player_b="Keegan Brown",
                stage="Group B",
            ),
        ),
    )

    completed_cards = (
        SimpleNamespace(
            match_id=20009,
            match_number=19,
            player_a_name="Henry Cooper",
            player_b_name="Chas Barstow",
        ),
        SimpleNamespace(
            match_id=20011,
            match_number=20,
            player_a_name="Richie Howson",
            player_b_name="Keegan Brown",
        ),
    )

    from app.services.modus_anchor_reconciliation_service import (
        VerifiedSequenceAnchor,
        build_anchor_aware_stale_reconciliation_plan,
    )

    plan = build_anchor_aware_stale_reconciliation_plan(
        group,
        completed_cards,
        anchors=(
            VerifiedSequenceAnchor(
                fixture_id=17829,
                real_match_id=74772858,
            ),
        ),
    )

    assert not plan.resolved
    assert plan.mappings == ()
    assert plan.unmatched_fixture_ids == ()


def test_discovers_verified_anchor_when_fixture_has_provisional_and_real_mapping():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    try:
        match = Match(
            id=17829,
            date=date(2026, 9, 19),
            tournament="MODUS Super Series",
            stage="Group B",
            match_format="Best of 7",
            status="completed",
            player_a="Henry Cooper",
            player_b="Chas Barstow",
            winner="Henry Cooper",
            score="4-2",
        )
        db.add(match)

        batch = HistoricalImportBatch(
            batch_uuid="anchor-scope-batch",
            filename="modus-series-26-week-197-Group B.html",
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
                internal_id=17829,
                external_id="modus-match-74772858",
                action="duplicate",
                created_by_batch=False,
            )
        )

        db.add_all(
            (
                ProviderEntityMapping(
                    provider="modus-official",
                    entity_type="fixture",
                    external_id="modus-match-74772858",
                    internal_id=17829,
                    competition_code="MODUS",
                ),
                ProviderEntityMapping(
                    provider="modus-official",
                    entity_type="fixture",
                    external_id="modus-match-20009",
                    internal_id=17829,
                    competition_code="MODUS",
                ),
            )
        )
        db.commit()

        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=197,
                group="Group B",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=17830,
                    fixture_date=date(2026, 9, 18),
                    player_a="Richie Howson",
                    player_b="Keegan Brown",
                    stage="Group B",
                ),
            ),
        )

        completed_cards = (
            SimpleNamespace(
                match_id=20009,
                match_number=19,
                player_a_name="Henry Cooper",
                player_b_name="Chas Barstow",
            ),
            SimpleNamespace(
                match_id=20011,
                match_number=20,
                player_a_name="Richie Howson",
                player_b_name="Keegan Brown",
            ),
        )

        from app.services.modus_anchor_reconciliation_service import (
            VerifiedSequenceAnchor,
            discover_verified_sequence_anchors,
        )

        anchors = discover_verified_sequence_anchors(
            db,
            group,
            completed_cards,
        )

        assert anchors == (
            VerifiedSequenceAnchor(
                fixture_id=17829,
                real_match_id=20009,
            ),
        )
    finally:
        db.close()


def test_discovery_rejects_anchor_with_intervening_same_scope_fixture():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    try:
        db.add_all(
            (
                Match(
                    id=100,
                    date=date(2026, 9, 19),
                    tournament="MODUS Super Series",
                    stage="Group B",
                    status="completed",
                    player_a="Henry Cooper",
                    player_b="Chas Barstow",
                ),
                Match(
                    id=101,
                    date=date(2026, 9, 19),
                    tournament="MODUS Super Series",
                    stage="Group B",
                    status="completed",
                    player_a="Other Player",
                    player_b="Another Player",
                ),
            )
        )

        batch = HistoricalImportBatch(
            batch_uuid="anchor-intervening-batch",
            filename="modus-series-26-week-197-Group B.html",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
        )
        db.add(batch)
        db.flush()

        db.add_all(
            (
                HistoricalImportItem(
                    batch_id=batch.id,
                    entity_type="fixture",
                    internal_id=100,
                    external_id="modus-match-20009",
                    action="updated",
                    created_by_batch=False,
                ),
                HistoricalImportItem(
                    batch_id=batch.id,
                    entity_type="fixture",
                    internal_id=101,
                    external_id="modus-match-99999",
                    action="duplicate",
                    created_by_batch=False,
                ),
            )
        )

        db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-20009",
                internal_id=100,
                competition_code="MODUS",
            )
        )
        db.commit()

        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=197,
                group="Group B",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=102,
                    fixture_date=date(2026, 9, 19),
                    player_a="Richie Howson",
                    player_b="Keegan Brown",
                    stage="Group B",
                ),
            ),
        )

        completed_cards = (
            SimpleNamespace(
                match_id=20009,
                match_number=19,
                player_a_name="Henry Cooper",
                player_b_name="Chas Barstow",
            ),
            SimpleNamespace(
                match_id=20011,
                match_number=20,
                player_a_name="Richie Howson",
                player_b_name="Keegan Brown",
            ),
        )

        from app.services.modus_anchor_reconciliation_service import (
            discover_verified_sequence_anchors,
        )

        assert discover_verified_sequence_anchors(
            db,
            group,
            completed_cards,
        ) == ()
    finally:
        db.close()


def test_discovery_rejects_verified_mapping_when_players_do_not_match_card():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    try:
        db.add(
            Match(
                id=100,
                date=date(2026, 9, 19),
                tournament="MODUS Super Series",
                stage="Group B",
                status="completed",
                player_a="Wrong Player",
                player_b="Another Wrong Player",
            )
        )

        batch = HistoricalImportBatch(
            batch_uuid="anchor-player-mismatch-batch",
            filename="modus-series-26-week-197-Group B.html",
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
                internal_id=100,
                external_id="modus-match-20009",
                action="updated",
                created_by_batch=False,
            )
        )

        db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-20009",
                internal_id=100,
                competition_code="MODUS",
            )
        )
        db.commit()

        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=197,
                group="Group B",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=101,
                    fixture_date=date(2026, 9, 19),
                    player_a="Richie Howson",
                    player_b="Keegan Brown",
                    stage="Group B",
                ),
            ),
        )

        completed_cards = (
            SimpleNamespace(
                match_id=20009,
                match_number=19,
                player_a_name="Henry Cooper",
                player_b_name="Chas Barstow",
            ),
            SimpleNamespace(
                match_id=20011,
                match_number=20,
                player_a_name="Richie Howson",
                player_b_name="Keegan Brown",
            ),
        )

        from app.services.modus_anchor_reconciliation_service import (
            discover_verified_sequence_anchors,
        )

        assert discover_verified_sequence_anchors(
            db,
            group,
            completed_cards,
        ) == ()
    finally:
        db.close()


def test_discovery_rejects_anchor_from_different_scope():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    try:
        db.add(
            Match(
                id=100,
                date=date(2026, 9, 12),
                tournament="MODUS Super Series",
                stage="Group B",
                status="completed",
                player_a="Henry Cooper",
                player_b="Chas Barstow",
            )
        )

        batch = HistoricalImportBatch(
            batch_uuid="anchor-wrong-scope-batch",
            filename="modus-series-26-week-196-Group B.html",
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
                internal_id=100,
                external_id="modus-match-20009",
                action="updated",
                created_by_batch=False,
            )
        )

        db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-20009",
                internal_id=100,
                competition_code="MODUS",
            )
        )

        db.commit()

        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=197,
                group="Group B",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=101,
                    fixture_date=date(2026, 9, 19),
                    player_a="Richie Howson",
                    player_b="Keegan Brown",
                    stage="Group B",
                ),
            ),
        )

        completed_cards = (
            SimpleNamespace(
                match_id=20009,
                match_number=19,
                player_a_name="Henry Cooper",
                player_b_name="Chas Barstow",
            ),
            SimpleNamespace(
                match_id=20011,
                match_number=20,
                player_a_name="Richie Howson",
                player_b_name="Keegan Brown",
            ),
        )

        from app.services.modus_anchor_reconciliation_service import (
            discover_verified_sequence_anchors,
        )

        anchors = discover_verified_sequence_anchors(
            db,
            group,
            completed_cards,
        )

        assert anchors == ()
    finally:
        db.close()
