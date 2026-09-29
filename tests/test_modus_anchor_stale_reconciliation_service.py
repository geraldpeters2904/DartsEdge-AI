from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
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


def _fixture(fixture_id, player_a, player_b):
    return ScopedStaleFixture(
        fixture_id=fixture_id,
        fixture_date=date(2026, 9, 19),
        player_a=player_a,
        player_b=player_b,
        stage="Group B",
    )


def _card(match_id, match_number, player_a, player_b):
    return SimpleNamespace(
        match_id=match_id,
        match_number=match_number,
        player_a_name=player_a,
        player_b_name=player_b,
    )


def test_normal_plan_wins_without_anchor_fallback():
    group = _group(
        _fixture(100, "Alpha", "Bravo"),
        _fixture(101, "Charlie", "Delta"),
    )
    cards = (
        _card(2001, 1, "Bravo", "Alpha"),
        _card(2002, 2, "Charlie", "Delta"),
    )

    from app.services.modus_anchor_stale_reconciliation_service import (
        reconcile_stale_scope_groups_with_verified_anchors,
    )

    with patch(
        "app.services.modus_anchor_stale_reconciliation_service."
        "discover_verified_sequence_anchors"
    ) as discover:
        results = reconcile_stale_scope_groups_with_verified_anchors(
            object(),
            (group,),
            fetch_cards=lambda scope: cards,
        )

    assert results[0].plan.resolved
    assert results[0].plan.mappings == (
        (100, 2001),
        (101, 2002),
    )
    discover.assert_not_called()


def test_unresolved_normal_plan_uses_verified_anchor_fallback():
    group = _group(
        _fixture(17830, "Richie Howson", "Keegan Brown"),
        _fixture(17855, "Richie Howson", "Keegan Brown"),
    )
    cards = (
        _card(19945, 1, "Keegan Brown", "Richie Howson"),
        _card(20009, 19, "Henry Cooper", "Chas Barstow"),
        _card(20011, 20, "Richie Howson", "Keegan Brown"),
    )

    from app.services.modus_anchor_reconciliation_service import (
        VerifiedSequenceAnchor,
    )
    from app.services.modus_anchor_stale_reconciliation_service import (
        reconcile_stale_scope_groups_with_verified_anchors,
    )

    with patch(
        "app.services.modus_anchor_stale_reconciliation_service."
        "discover_verified_sequence_anchors",
        return_value=(
            VerifiedSequenceAnchor(
                fixture_id=17829,
                real_match_id=20009,
            ),
        ),
    ):
        results = reconcile_stale_scope_groups_with_verified_anchors(
            object(),
            (group,),
            fetch_cards=lambda scope: cards,
        )

    assert results[0].plan.resolved
    assert results[0].plan.mappings == ((17830, 20011),)
    assert results[0].plan.unmatched_fixture_ids == (17855,)


def test_fetch_failure_remains_quarantined():
    group = _group(
        _fixture(200, "Echo", "Foxtrot"),
    )

    from app.services.modus_anchor_stale_reconciliation_service import (
        reconcile_stale_scope_groups_with_verified_anchors,
    )

    def fetch_cards(scope):
        raise RuntimeError("MODUS page unavailable")

    results = reconcile_stale_scope_groups_with_verified_anchors(
        object(),
        (group,),
        fetch_cards=fetch_cards,
    )

    assert not results[0].plan.resolved
    assert results[0].plan.mappings == ()
    assert "MODUS page unavailable" in (results[0].error or "")
