from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.canonical_data import ProviderEntityMapping
from app.services.modus_verified_mapping_service import (
    replace_with_verified_modus_mapping,
)


class ModusVerifiedMappingServiceTests(unittest.TestCase):

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def _mapping(
        self,
        external_id,
        internal_id,
    ):
        row = ProviderEntityMapping(
            provider="modus-official",
            entity_type="fixture",
            external_id=external_id,
            internal_id=internal_id,
            competition_code="MODUS",
        )
        self.db.add(row)
        self.db.flush()
        return row

    def test_replaces_provisional_mapping_with_verified_mapping(self):
        self._mapping(
            "modus-match-74325910",
            100,
        )
        self.db.commit()

        replace_with_verified_modus_mapping(
            self.db,
            fixture_id=100,
            real_match_id=19695,
        )
        self.db.commit()

        rows = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=100,
            )
            .all()
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].external_id,
            "modus-match-19695",
        )

    def test_refuses_verified_id_owned_by_another_fixture(self):
        self._mapping(
            "modus-match-74325910",
            100,
        )
        self._mapping(
            "modus-match-19695",
            200,
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            replace_with_verified_modus_mapping(
                self.db,
                fixture_id=100,
                real_match_id=19695,
            )

        self.db.rollback()

        provisional = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-74325910",
            )
            .one()
        )

        self.assertEqual(
            provisional.internal_id,
            100,
        )

    def test_existing_verified_mapping_is_idempotent(self):
        self._mapping(
            "modus-match-19695",
            100,
        )
        self.db.commit()

        replace_with_verified_modus_mapping(
            self.db,
            fixture_id=100,
            real_match_id=19695,
        )
        self.db.commit()

        rows = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=100,
            )
            .all()
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].external_id,
            "modus-match-19695",
        )


if __name__ == "__main__":
    unittest.main()
