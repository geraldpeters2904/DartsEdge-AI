import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.forward_schedule_discovery_service import (
    _future_modus_fixture_count,
    _target_failure_result,
    _target_success_result,
)


class ForwardScheduleDiscoveryDiagnosticTests(
    unittest.TestCase
):
    def test_success_result_records_imported_target(self):
        result = SimpleNamespace(
            imported=True,
            unchanged=False,
            action="imported",
            source_url="https://example.test/source",
            current_url="https://example.test/current",
            page_title="MODUS",
            message="Imported.",
            import_result=SimpleNamespace(
                fixture_count=12,
            ),
        )

        target = _target_success_result(
            group="Group A",
            result=result,
        )

        self.assertEqual(
            target.group,
            "Group A",
        )
        self.assertEqual(
            target.state,
            "IMPORTED",
        )
        self.assertTrue(
            target.imported
        )
        self.assertEqual(
            target.fixture_count,
            12,
        )
        self.assertIsNone(
            target.error
        )

    def test_success_result_records_unchanged_target(self):
        result = SimpleNamespace(
            imported=False,
            unchanged=True,
            action="unchanged",
            source_url="https://example.test/source",
            current_url="https://example.test/current",
            page_title="MODUS",
            message="Unchanged.",
            import_result=None,
        )

        target = _target_success_result(
            group="Group B",
            result=result,
        )

        self.assertEqual(
            target.state,
            "UNCHANGED",
        )
        self.assertFalse(
            target.imported
        )
        self.assertTrue(
            target.unchanged
        )
        self.assertIsNone(
            target.fixture_count
        )

    def test_failure_result_preserves_group_and_error(self):
        target = _target_failure_result(
            group="Group C",
            exc=RuntimeError(
                "fixture cards timed out"
            ),
        )

        self.assertEqual(
            target.group,
            "Group C",
        )
        self.assertEqual(
            target.state,
            "FAILED",
        )
        self.assertFalse(
            target.imported
        )
        self.assertFalse(
            target.unchanged
        )
        self.assertIn(
            "RuntimeError",
            target.error,
        )
        self.assertIn(
            "fixture cards timed out",
            target.error,
        )

    def test_actionable_fixture_count_includes_today(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            bind=engine
        )

        Session = sessionmaker(
            bind=engine
        )

        db = Session()

        try:
            current_day = date(
                2026,
                8,
                13,
            )

            db.add_all(
                [
                    Match(
                        date=current_day,
                        tournament="MODUS Super Series",
                        status="scheduled",
                        player_a="Today A",
                        player_b="Today B",
                    ),
                    Match(
                        date=(
                            current_day
                            + timedelta(days=1)
                        ),
                        tournament="MODUS Super Series",
                        status="scheduled",
                        player_a="Tomorrow A",
                        player_b="Tomorrow B",
                    ),
                    Match(
                        date=(
                            current_day
                            - timedelta(days=1)
                        ),
                        tournament="MODUS Super Series",
                        status="scheduled",
                        player_a="Past A",
                        player_b="Past B",
                    ),
                    Match(
                        date=current_day,
                        tournament="MODUS Super Series",
                        status="completed",
                        player_a="Done A",
                        player_b="Done B",
                    ),
                    Match(
                        date=current_day,
                        tournament="OTHER",
                        status="scheduled",
                        player_a="Other A",
                        player_b="Other B",
                    ),
                ]
            )

            db.commit()

            count = _future_modus_fixture_count(
                db,
                today=current_day,
            )

            self.assertEqual(
                count,
                2,
            )

        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
