import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.selected_offset = 0
        self.selected_limit = None

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, value):
        self.selected_offset = int(value)
        return self

    def limit(self, value):
        self.selected_limit = int(value)
        return self

    def all(self):
        rows = self.rows[self.selected_offset:]

        if self.selected_limit is not None:
            rows = rows[:self.selected_limit]

        return rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *args, **kwargs):
        return FakeQuery(self.rows)


class CurrentMatchEnrichmentV33ValidationServiceTests(
    unittest.TestCase
):
    def test_select_match_ids_honours_offset_and_limit(self):
        db = FakeDb([
            (101,),
            (102,),
            (103,),
            (104,),
        ])

        ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=1,
                limit=2,
            )
        )

        self.assertEqual(
            ids,
            [102, 103],
        )

    def test_rejects_negative_offset(self):
        service = (
            CurrentMatchEnrichmentV33ValidationService(
                snapshot_engine=object(),
                prediction_engine=object(),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "offset cannot be negative",
        ):
            service.validate(
                FakeDb([]),
                offset=-1,
            )

    def test_rejects_non_positive_limit(self):
        service = (
            CurrentMatchEnrichmentV33ValidationService(
                snapshot_engine=object(),
                prediction_engine=object(),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "limit must be greater than zero",
        ):
            service.validate(
                FakeDb([]),
                limit=0,
            )

    def test_default_model_is_v33(self):
        service = (
            CurrentMatchEnrichmentV33ValidationService()
        )

        self.assertEqual(
            service.prediction_engine.MODEL_VERSION,
            "transparent-v3.3",
        )

    def test_default_snapshot_engine_is_advanced_historical(self):
        service = (
            CurrentMatchEnrichmentV33ValidationService()
        )

        self.assertEqual(
            service.snapshot_engine.__class__.__name__,
            "AdvancedHistoricalSnapshotEngine",
        )


if __name__ == "__main__":
    unittest.main()


class CurrentMatchEnrichmentV33EligibleSelectionTests(
    unittest.TestCase
):
    def test_selector_excludes_completed_rows_without_valid_winner(
        self,
    ):
        from datetime import date

        from app.models.match import Match
        from tests.helpers.database import (
            create_test_session,
        )

        db = create_test_session()

        try:
            db.add_all(
                [
                    Match(
                        date=date(2026, 8, 1),
                        status="completed",
                        player_a="A",
                        player_b="B",
                        winner=None,
                    ),
                    Match(
                        date=date(2026, 8, 2),
                        status="completed",
                        player_a="C",
                        player_b="D",
                        winner="Someone Else",
                    ),
                    Match(
                        date=date(2026, 8, 3),
                        status="completed",
                        player_a="E",
                        player_b="F",
                        winner="E",
                    ),
                    Match(
                        date=date(2026, 8, 4),
                        status="completed",
                        player_a="G",
                        player_b="H",
                        winner="H",
                    ),
                ]
            )

            db.commit()

            ids = (
                CurrentMatchEnrichmentV33ValidationService
                ._select_match_ids(
                    db,
                    offset=0,
                    limit=10,
                )
            )

            rows = (
                db.query(Match)
                .filter(
                    Match.id.in_(ids)
                )
                .order_by(Match.date.asc())
                .all()
            )

            self.assertEqual(
                [
                    row.winner
                    for row in rows
                ],
                [
                    "E",
                    "H",
                ],
            )

        finally:
            db.close()
