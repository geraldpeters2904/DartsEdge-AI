import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.live_odds_collector_service import (
    LiveOddsCollector,
)


class LiveOddsCollectorTests(
    unittest.TestCase
):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )
        Base.metadata.create_all(
            bind=engine
        )

        Session = sessionmaker(
            bind=engine
        )
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_collects_multiple_bookmakers(
        self,
    ):
        collector = LiveOddsCollector(
            fetchers={
                "paddypower": lambda: [
                    {
                        "fixture_id": 701,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": 2.10,
                    }
                ],
                "bet365": lambda: [
                    {
                        "fixture_id": 701,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": 2.05,
                    }
                ],
            }
        )

        report = collector.collect_once(
            self.db
        )

        self.assertTrue(
            report.success
        )

        self.assertEqual(
            report.bookmakers_attempted,
            2,
        )

        self.assertEqual(
            report.bookmakers_succeeded,
            2,
        )

        self.assertEqual(
            report.snapshots_created,
            2,
        )

        self.assertEqual(
            self.db.query(
                OddsSnapshot
            ).count(),
            2,
        )

    def test_failure_isolated_to_one_bookmaker(
        self,
    ):
        def fail():
            raise RuntimeError(
                "source unavailable"
            )

        collector = LiveOddsCollector(
            fetchers={
                "paddypower": lambda: [
                    {
                        "fixture_id": 702,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": 2.20,
                    }
                ],
                "bet365": fail,
            }
        )

        report = collector.collect_once(
            self.db
        )

        self.assertFalse(
            report.success
        )

        self.assertEqual(
            report.bookmakers_succeeded,
            1,
        )

        self.assertEqual(
            report.bookmakers_failed,
            1,
        )

        self.assertEqual(
            report.snapshots_created,
            1,
        )

        failed = [
            item
            for item in report.bookmaker_results
            if not item.success
        ]

        self.assertEqual(
            len(failed),
            1,
        )

        self.assertIn(
            "source unavailable",
            failed[0].error,
        )

    def test_second_cycle_records_movements(
        self,
    ):
        state = {
            "paddy": 2.10,
        }

        collector = LiveOddsCollector(
            fetchers={
                "paddypower": lambda: [
                    {
                        "fixture_id": 703,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": state[
                            "paddy"
                        ],
                    }
                ]
            }
        )

        first = collector.collect_once(
            self.db
        )

        self.assertEqual(
            first.movements_created,
            0,
        )

        state["paddy"] = 2.00

        second = collector.collect_once(
            self.db
        )

        self.assertEqual(
            second.movements_created,
            1,
        )

        self.assertEqual(
            self.db.query(
                OddsMovement
            ).count(),
            1,
        )

    def test_unchanged_prices_are_suppressed(
        self,
    ):
        collector = LiveOddsCollector(
            fetchers={
                "paddypower": lambda: [
                    {
                        "fixture_id": 704,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": 2.00,
                    }
                ]
            }
        )

        collector.collect_once(
            self.db
        )

        second = collector.collect_once(
            self.db
        )

        self.assertEqual(
            second.snapshots_created,
            0,
        )

        self.assertEqual(
            second.unchanged,
            1,
        )


if __name__ == "__main__":
    unittest.main()
