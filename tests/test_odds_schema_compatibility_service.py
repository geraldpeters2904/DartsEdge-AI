import unittest
from datetime import date, datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services.odds_schema_compatibility_service import (
    _normalise_bookmaker,
)


class OddsSchemaCompatibilityTests(
    unittest.TestCase
):
    def test_bookmaker_normalisation(
        self,
    ):
        self.assertEqual(
            _normalise_bookmaker(
                "Paddy Power"
            ),
            "paddypower",
        )

    def test_model_exposes_legacy_and_new_fields(
        self,
    ):
        columns = {
            column.name
            for column
            in OddsSnapshot.__table__.columns
        }

        for name in (
            "fixture_id",
            "bookmaker_code",
            "implied_probability",
            "source_reference",
            "fixture_date",
            "player_a",
            "player_b",
            "bookmaker",
            "provider_id",
        ):
            self.assertIn(
                name,
                columns,
            )


if __name__ == "__main__":
    unittest.main()
