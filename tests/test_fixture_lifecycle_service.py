import unittest
from datetime import date
from types import SimpleNamespace

from app.services.fixture_lifecycle_service import (
    CurrentSeriesLifecycleManager,
    FixtureLifecycleRecord,
    synchronise_fixture_records,
)


class FakeQuery:
    def __init__(
        self,
        rows,
    ):
        self.rows = rows

    def filter(
        self,
        *args,
    ):
        return self

    def all(
        self,
    ):
        return list(
            self.rows
        )


class FakeDb:
    def __init__(
        self,
        rows=None,
    ):
        self.rows = list(
            rows
            or []
        )
        self.commits = 0

    def query(
        self,
        model,
    ):
        return FakeQuery(
            self.rows
        )

    def add(
        self,
        row,
    ):
        row.id = len(
            self.rows
        ) + 1
        self.rows.append(
            row
        )

    def commit(
        self,
    ):
        self.commits += 1


class FixtureLifecycleServiceTests(
    unittest.TestCase
):
    def test_creates_new_fixture(self):
        db = FakeDb()

        report = (
            synchronise_fixture_records(
                db,
                [
                    FixtureLifecycleRecord(
                        fixture_date=date(
                            2026,
                            8,
                            7,
                        ),
                        tournament="MODUS",
                        player_a="Alpha",
                        player_b="Bravo",
                        status="scheduled",
                    )
                ],
                window_start=date(
                    2026,
                    8,
                    1,
                ),
                window_end=date(
                    2026,
                    8,
                    14,
                ),
            )
        )

        self.assertEqual(
            report.created,
            1,
        )

        self.assertEqual(
            len(
                db.rows
            ),
            1,
        )

    def test_updates_scheduled_to_completed(self):
        existing = (
            SimpleNamespace(
                id=1,
                date=date(
                    2026,
                    8,
                    7,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
                stage=None,
                match_format=None,
            )
        )

        db = FakeDb([
            existing
        ])

        report = (
            synchronise_fixture_records(
                db,
                [
                    FixtureLifecycleRecord(
                        fixture_date=date(
                            2026,
                            8,
                            7,
                        ),
                        tournament="MODUS",
                        player_a="Alpha",
                        player_b="Bravo",
                        status="completed",
                    )
                ],
                window_start=date(
                    2026,
                    8,
                    1,
                ),
                window_end=date(
                    2026,
                    8,
                    14,
                ),
            )
        )

        self.assertEqual(
            report.updated,
            1,
        )

        self.assertEqual(
            report.completed,
            1,
        )

        self.assertEqual(
            existing.status,
            "completed",
        )

    def test_repeated_sync_is_idempotent(self):
        existing = (
            SimpleNamespace(
                id=1,
                date=date(
                    2026,
                    8,
                    7,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="completed",
                stage=None,
                match_format=None,
            )
        )

        db = FakeDb([
            existing
        ])

        report = (
            synchronise_fixture_records(
                db,
                [
                    FixtureLifecycleRecord(
                        fixture_date=date(
                            2026,
                            8,
                            7,
                        ),
                        tournament="MODUS",
                        player_a="Alpha",
                        player_b="Bravo",
                        status="completed",
                    )
                ],
                window_start=date(
                    2026,
                    8,
                    1,
                ),
                window_end=date(
                    2026,
                    8,
                    14,
                ),
            )
        )

        self.assertEqual(
            report.unchanged,
            1,
        )

        self.assertEqual(
            report.updated,
            0,
        )

    def test_manager_uses_rolling_window(self):
        seen = {}

        def fetch(
            start,
            end,
        ):
            seen[
                "start"
            ] = start
            seen[
                "end"
            ] = end
            return []

        manager = (
            CurrentSeriesLifecycleManager(
                fetch_records=fetch,
                past_days=7,
                future_days=7,
            )
        )

        db = FakeDb()

        manager.sync_once(
            db,
            anchor_date=date(
                2026,
                8,
                7,
            ),
        )

        self.assertEqual(
            seen[
                "start"
            ],
            date(
                2026,
                7,
                31,
            ),
        )

        self.assertEqual(
            seen[
                "end"
            ],
            date(
                2026,
                8,
                14,
            ),
        )


if __name__ == "__main__":
    unittest.main()


class FixtureLifecycleDuplicateRegressionTests(unittest.TestCase):
    def test_cancelled_duplicate_cannot_overwrite_completed_result(self):
        fixture_date = date(2026, 10, 20)

        original = SimpleNamespace(
            id=18287,
            date=fixture_date,
            tournament="MODUS",
            player_a="Ricardo Ulrich",
            player_b="Archie Self",
            status="completed",
            winner="Archie Self",
            score_a=2,
            score_b=4,
            stage=None,
            match_format=None,
            provider_id=None,
        )

        duplicate = SimpleNamespace(
            id=18314,
            date=fixture_date,
            tournament="MODUS",
            player_a="Ricardo Ulrich",
            player_b="Archie Self",
            status="cancelled",
            winner=None,
            score_a=None,
            score_b=None,
            stage=None,
            match_format=None,
            provider_id=None,
        )

        db = FakeDb([original, duplicate])

        report = synchronise_fixture_records(
            db,
            [
                FixtureLifecycleRecord(
                    fixture_date=fixture_date,
                    tournament="MODUS",
                    player_a=duplicate.player_a,
                    player_b=duplicate.player_b,
                    status="cancelled",
                )
            ],
            window_start=date(2026, 10, 19),
            window_end=date(2026, 10, 21),
        )

        self.assertEqual(original.status, "completed")
        self.assertEqual(original.winner, "Archie Self")
        self.assertEqual(original.score_a, 2)
        self.assertEqual(original.score_b, 4)
        self.assertEqual(duplicate.status, "cancelled")
        self.assertEqual(report.updated, 0)


class FixtureLifecycleExactIdentityTests(unittest.TestCase):
    def test_duplicate_updates_only_its_own_database_id(self):
        fixture_date = date(2026, 10, 20)

        original = SimpleNamespace(
            id=18287,
            date=fixture_date,
            tournament="MODUS",
            player_a="Ricardo Ulrich",
            player_b="Archie Self",
            status="completed",
            winner="Archie Self",
            score_a=2,
            score_b=4,
            stage=None,
            match_format=None,
            provider_id=None,
        )

        duplicate = SimpleNamespace(
            id=18314,
            date=fixture_date,
            tournament="MODUS",
            player_a="Ricardo Ulrich",
            player_b="Archie Self",
            status="scheduled",
            winner=None,
            score_a=None,
            score_b=None,
            stage=None,
            match_format=None,
            provider_id=None,
        )

        db = FakeDb([original, duplicate])

        report = synchronise_fixture_records(
            db,
            [
                FixtureLifecycleRecord(
                    match_id=18314,
                    fixture_date=fixture_date,
                    tournament="MODUS",
                    player_a="Ricardo Ulrich",
                    player_b="Archie Self",
                    status="cancelled",
                )
            ],
            window_start=date(2026, 10, 19),
            window_end=date(2026, 10, 21),
        )

        self.assertEqual(original.status, "completed")
        self.assertEqual(duplicate.status, "cancelled")
        self.assertEqual(original.winner, "Archie Self")
        self.assertEqual(report.updated, 1)


class FixtureLifecycleMissingIdentityTests(unittest.TestCase):
    def test_missing_database_id_does_not_create_duplicate(self):
        fixture_date = date(2026, 10, 20)

        original = SimpleNamespace(
            id=18287,
            date=fixture_date,
            tournament="MODUS",
            player_a="Ricardo Ulrich",
            player_b="Archie Self",
            status="completed",
            winner="Archie Self",
            score_a=2,
            score_b=4,
            stage=None,
            match_format=None,
            provider_id=None,
        )

        db = FakeDb([original])

        report = synchronise_fixture_records(
            db,
            [
                FixtureLifecycleRecord(
                    match_id=999999,
                    fixture_date=fixture_date,
                    tournament="MODUS",
                    player_a="Ricardo Ulrich",
                    player_b="Archie Self",
                    status="cancelled",
                )
            ],
            window_start=date(2026, 10, 19),
            window_end=date(2026, 10, 21),
        )

        self.assertEqual(len(db.rows), 1)
        self.assertEqual(original.status, "completed")
        self.assertEqual(report.created, 0)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(db.commits, 0)
