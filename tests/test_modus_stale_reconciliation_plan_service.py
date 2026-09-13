from __future__ import annotations

import unittest
from datetime import date

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)
from app.services.modus_stale_reconciliation_plan_service import (
    build_stale_reconciliation_plan,
)


class Card:
    def __init__(
        self,
        match_id,
        match_number,
        player_a_name,
        player_b_name,
    ):
        self.match_id = match_id
        self.match_number = match_number
        self.player_a_name = player_a_name
        self.player_b_name = player_b_name


class ModusStaleReconciliationPlanTests(unittest.TestCase):

    def test_builds_unique_verified_plan(self):
        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=196,
                group="Group A",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=100,
                    fixture_date=date(2026, 9, 7),
                    player_a="Alpha",
                    player_b="Bravo",
                    stage="Group A",
                ),
                ScopedStaleFixture(
                    fixture_id=101,
                    fixture_date=date(2026, 9, 7),
                    player_a="Ghost",
                    player_b="Player",
                    stage="Group A",
                ),
                ScopedStaleFixture(
                    fixture_id=102,
                    fixture_date=date(2026, 9, 7),
                    player_a="Charlie",
                    player_b="Delta",
                    stage="Group A",
                ),
            ),
        )

        cards = (
            Card(2001, 1, "Bravo", "Alpha"),
            Card(2002, 2, "Charlie", "Delta"),
        )

        plan = build_stale_reconciliation_plan(
            group,
            cards,
        )

        self.assertTrue(plan.resolved)
        self.assertEqual(
            plan.mappings,
            (
                (100, 2001),
                (102, 2002),
            ),
        )
        self.assertEqual(
            plan.unmatched_fixture_ids,
            (101,),
        )

    def test_ambiguous_sequence_produces_no_plan(self):
        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=196,
                group="Group A",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=100,
                    fixture_date=date(2026, 9, 7),
                    player_a="Alpha",
                    player_b="Bravo",
                    stage="Group A",
                ),
                ScopedStaleFixture(
                    fixture_id=101,
                    fixture_date=date(2026, 9, 7),
                    player_a="Alpha",
                    player_b="Bravo",
                    stage="Group A",
                ),
                ScopedStaleFixture(
                    fixture_id=102,
                    fixture_date=date(2026, 9, 7),
                    player_a="Charlie",
                    player_b="Delta",
                    stage="Group A",
                ),
            ),
        )

        cards = (
            Card(2001, 1, "Alpha", "Bravo"),
            Card(2002, 2, "Charlie", "Delta"),
        )

        plan = build_stale_reconciliation_plan(
            group,
            cards,
        )

        self.assertFalse(plan.resolved)
        self.assertEqual(plan.mappings, ())
        self.assertEqual(plan.unmatched_fixture_ids, ())


if __name__ == "__main__":
    unittest.main()


def test_finds_unique_completed_window_inside_larger_scope():
    group = StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=196,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=300,
                fixture_date=date(2026, 9, 10),
                player_a="Alpha",
                player_b="Bravo",
                stage="Group B",
            ),
            ScopedStaleFixture(
                fixture_id=301,
                fixture_date=date(2026, 9, 10),
                player_a="Charlie",
                player_b="Delta",
                stage="Group B",
            ),
        ),
    )

    cards = (
        Card(4001, 1, "Echo", "Foxtrot"),
        Card(4002, 2, "Bravo", "Alpha"),
        Card(4003, 3, "Charlie", "Delta"),
        Card(4004, 4, "Golf", "Hotel"),
    )

    plan = build_stale_reconciliation_plan(
        group,
        cards,
    )

    assert plan.resolved
    assert plan.mappings == (
        (300, 4002),
        (301, 4003),
    )
    assert plan.unmatched_fixture_ids == ()


def test_multiple_matching_completed_windows_are_rejected():
    group = StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=196,
            group="Group B",
        ),
        fixtures=(
            ScopedStaleFixture(
                fixture_id=500,
                fixture_date=date(2026, 9, 10),
                player_a="Alpha",
                player_b="Bravo",
                stage="Group B",
            ),
            ScopedStaleFixture(
                fixture_id=501,
                fixture_date=date(2026, 9, 10),
                player_a="Charlie",
                player_b="Delta",
                stage="Group B",
            ),
        ),
    )

    cards = (
        Card(6001, 1, "Alpha", "Bravo"),
        Card(6002, 2, "Charlie", "Delta"),
        Card(6003, 3, "Echo", "Foxtrot"),
        Card(6004, 4, "Bravo", "Alpha"),
        Card(6005, 5, "Delta", "Charlie"),
    )

    plan = build_stale_reconciliation_plan(
        group,
        cards,
    )

    assert not plan.resolved
    assert plan.mappings == ()
    assert plan.unmatched_fixture_ids == ()
