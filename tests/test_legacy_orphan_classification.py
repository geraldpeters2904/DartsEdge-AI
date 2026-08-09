import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.forward_fixture_catchup_service import (
    stale_scheduled_modus_fixtures,
)


class LegacyOrphanClassificationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_unmapped_past_fixture_is_legacy_orphan(self):
        self.db.add(
            Match(
                id=1,
                date=date(2026, 7, 15),
                tournament="MODUS",
                player_a="Lewis Pride",
                player_b="Devon Petersen",
                status="scheduled",
            )
        )
        self.db.commit()

        rows = stale_scheduled_modus_fixtures(
            self.db,
            today=date(2026, 8, 9),
        )

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].has_fixture_mapping)
        self.assertEqual(
            rows[0].classification,
            "LEGACY_ORPHAN",
        )


if __name__ == "__main__":
    unittest.main()
