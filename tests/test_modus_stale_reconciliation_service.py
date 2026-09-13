from __future__ import annotations

import unittest
from datetime import date

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)
from app.services.modus_stale_reconciliation_service import (
    reconcile_stale_scope_groups,
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


class ModusStaleReconciliationServiceTests(unittest.TestCase):

    def test_builds_plan_for_each_scope(self):
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
                    player_a="Charlie",
                    player_b="Delta",
                    stage="Group A",
                ),
            ),
        )

        calls = []

        def fetch_cards(scope):
            calls.append(scope)
            return (
                Card(2001, 1, "Bravo", "Alpha"),
                Card(2002, 2, "Charlie", "Delta"),
            )

        results = reconcile_stale_scope_groups(
            (group,),
            fetch_cards=fetch_cards,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(calls, [group.scope])

        result = results[0]

        self.assertEqual(result.scope, group.scope)
        self.assertTrue(result.plan.resolved)
        self.assertEqual(
            result.plan.mappings,
            (
                (100, 2001),
                (101, 2002),
            ),
        )

    def test_fetch_failure_is_quarantined(self):
        group = StaleFixtureScopeGroup(
            scope=ModusImportScope(
                series_id=26,
                week_id=196,
                group="Group B",
            ),
            fixtures=(
                ScopedStaleFixture(
                    fixture_id=200,
                    fixture_date=date(2026, 9, 8),
                    player_a="Echo",
                    player_b="Foxtrot",
                    stage="Group B",
                ),
            ),
        )

        def fetch_cards(scope):
            raise RuntimeError("MODUS page unavailable")

        results = reconcile_stale_scope_groups(
            (group,),
            fetch_cards=fetch_cards,
        )

        self.assertEqual(len(results), 1)

        result = results[0]

        self.assertEqual(result.scope, group.scope)
        self.assertFalse(result.plan.resolved)
        self.assertEqual(result.plan.mappings, ())
        self.assertIn(
            "MODUS page unavailable",
            result.error or "",
        )


if __name__ == "__main__":
    unittest.main()
