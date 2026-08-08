import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.bet365_adapter import (
    Bet365Adapter,
)
from app.services.bookmaker_adapter_registry import (
    default_bookmaker_registry,
)
from app.services.bookmaker_quote_ingestion_service import (
    ingest_bookmaker_payload,
)
from app.services.paddy_power_adapter import (
    PaddyPowerAdapter,
)


class BookmakerAdapterFrameworkTests(
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

    def test_registry_contains_primary_adapters(
        self,
    ):
        registry = (
            default_bookmaker_registry()
        )

        self.assertEqual(
            registry.available(),
            (
                "bet365",
                "paddypower",
            ),
        )

    def test_paddy_power_normalises_quote(
        self,
    ):
        adapter = (
            PaddyPowerAdapter()
        )

        captured = datetime(
            2026,
            8,
            8,
            9,
            0,
        )

        result = adapter.extract_quotes(
            [
                {
                    "fixture_id": 501,
                    "market": "Match Winner",
                    "selection": "  Alpha   Player ",
                    "decimal_odds": "2.10",
                }
            ],
            captured_at=captured,
        )

        quote = result.quotes[0]

        self.assertEqual(
            quote.bookmaker_code,
            "paddypower",
        )
        self.assertEqual(
            quote.market,
            "match_winner",
        )
        self.assertEqual(
            quote.selection,
            "Alpha Player",
        )
        self.assertEqual(
            quote.decimal_odds,
            2.10,
        )

    def test_bet365_rejects_invalid_price(
        self,
    ):
        adapter = Bet365Adapter()

        with self.assertRaises(
            ValueError
        ):
            adapter.extract_quotes(
                [
                    {
                        "fixture_id": 501,
                        "market": "match_winner",
                        "selection": "Alpha",
                        "decimal_odds": 1.0,
                    }
                ]
            )

    def test_ingestion_writes_snapshots_and_movement(
        self,
    ):
        first = [
            {
                "fixture_id": 501,
                "market": "match_winner",
                "selection": "Alpha",
                "decimal_odds": 2.10,
            }
        ]

        second = [
            {
                "fixture_id": 501,
                "market": "match_winner",
                "selection": "Alpha",
                "decimal_odds": 2.00,
            }
        ]

        ingest_bookmaker_payload(
            self.db,
            bookmaker_code="paddypower",
            payload=first,
        )

        report = ingest_bookmaker_payload(
            self.db,
            bookmaker_code="paddypower",
            payload=second,
        )

        self.assertEqual(
            report.snapshots_created,
            1,
        )

        self.assertEqual(
            report.movements_created,
            1,
        )

        self.assertEqual(
            self.db.query(
                OddsSnapshot
            ).count(),
            2,
        )

        self.assertEqual(
            self.db.query(
                OddsMovement
            ).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
