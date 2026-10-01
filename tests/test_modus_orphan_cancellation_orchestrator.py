from datetime import date

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_orphan_cancellation_orchestrator import (
    execute_unmatched_orphan_cancellations,
)
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)


def _fixture(fixture_id, player_a, player_b):
    return ScopedStaleFixture(
        fixture_id=fixture_id,
        fixture_date=date(2026, 9, 19),
        player_a=player_a,
        player_b=player_b,
        stage="Group B",
    )


def _group(*fixtures):
    return StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=tuple(fixtures),
    )


def test_orchestrator_never_reconsiders_fixture_not_in_unmatched_ids():
    group = _group(
        _fixture(
            17830,
            "Richie Howson",
            "Keegan Brown",
        ),
        _fixture(
            17855,
            "Richie Howson",
            "Keegan Brown",
        ),
    )

    class FailIfDatabaseIsTouched:
        def query(self, *args, **kwargs):
            raise AssertionError(
                "Database must not be touched when no supplied unmatched "
                "fixture exists in the stale group."
            )

    result = execute_unmatched_orphan_cancellations(
        FailIfDatabaseIsTouched(),
        group=group,
        unmatched_fixture_ids=(99999,),
        completed_cards=(),
    )

    assert result.attempted == 0
    assert result.cancelled == 0
    assert result.deferred == 1
    assert result.executions == ()
    assert len(result.errors) == 1


def test_real_shaped_unmatched_17855_is_cancelled_only_after_structural_proof():
    from app.models.canonical_data import DataProvenance
    from app.models.match import Match
    from tests.test_modus_orphan_cancellation_execution_service import (
        _database,
        _seed_eligible_candidate,
    )
    from tests.test_modus_orphan_cancellation_plan_service import (
        Card,
    )

    cards = (
        Card(19945, 1, "Keegan Brown", "Richie Howson"),
        Card(19946, 2, "Chas Barstow", "Henry Cooper"),
        Card(19948, 3, "Steve Green", "Keegan Brown"),
        Card(19950, 4, "Richie Howson", "Chas Barstow"),
        Card(19952, 5, "Henry Cooper", "Steve Green"),
        Card(19954, 6, "Keegan Brown", "Chas Barstow"),
        Card(19956, 7, "Richie Howson", "Henry Cooper"),
        Card(19958, 8, "Chas Barstow", "Steve Green"),
        Card(19960, 9, "Henry Cooper", "Keegan Brown"),
        Card(19962, 10, "Steve Green", "Richie Howson"),
        Card(19993, 11, "Richie Howson", "Steve Green"),
        Card(19995, 12, "Keegan Brown", "Henry Cooper"),
        Card(19997, 13, "Steve Green", "Chas Barstow"),
        Card(19999, 14, "Henry Cooper", "Richie Howson"),
        Card(20001, 15, "Chas Barstow", "Keegan Brown"),
        Card(20003, 16, "Steve Green", "Henry Cooper"),
        Card(20005, 17, "Chas Barstow", "Richie Howson"),
        Card(20007, 18, "Keegan Brown", "Steve Green"),
        Card(20009, 19, "Henry Cooper", "Chas Barstow"),
        Card(20011, 20, "Richie Howson", "Keegan Brown"),
    )

    db = _database()

    try:
        _seed_eligible_candidate(db)

        result = execute_unmatched_orphan_cancellations(
            db,
            group=_group(
                _fixture(
                    17855,
                    "Richie Howson",
                    "Keegan Brown",
                ),
            ),
            unmatched_fixture_ids=(17855,),
            completed_cards=cards,
        )

        assert result.attempted == 1
        assert result.cancelled == 1
        assert result.deferred == 0
        assert result.errors == ()
        assert len(result.executions) == 1
        assert result.executions[0].fixture_id == 17855

        match = (
            db.query(Match)
            .filter(Match.id == 17855)
            .one()
        )
        assert match.status == "cancelled"

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
        assert provenance.confidence == "derived"
    finally:
        db.rollback()
        db.close()
