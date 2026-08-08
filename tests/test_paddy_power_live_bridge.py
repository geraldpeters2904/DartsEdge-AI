import unittest
from types import SimpleNamespace

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
    _as_rows,
    _normalise_row,
    fetch_existing_paddy_power_quotes,
)


class PaddyPowerLiveBridgeTests(
    unittest.TestCase
):
    def test_normalises_mapping_row(
        self,
    ):
        row = _normalise_row(
            {
                "event_id": "9001",
                "market_name": "Match Winner",
                "runner": "Alpha Player",
                "price": "2.10",
                "url": "https://example.invalid/event",
            }
        )

        self.assertEqual(
            row["fixture_id"],
            9001,
        )
        self.assertEqual(
            row["selection"],
            "Alpha Player",
        )
        self.assertEqual(
            row["decimal_odds"],
            2.10,
        )

    def test_accepts_object_rows(
        self,
    ):
        rows = _as_rows(
            [
                SimpleNamespace(
                    fixture_id=9002,
                    market="match_winner",
                    selection="Bravo Player",
                    decimal_odds=1.91,
                )
            ]
        )

        self.assertEqual(
            rows[0]["fixture_id"],
            9002,
        )

    def test_fetch_uses_resolved_existing_callable(
        self,
    ):
        def fake_capture():
            return {
                "quotes": [
                    {
                        "fixture_id": 9003,
                        "market": "match_winner",
                        "selection": "Charlie Player",
                        "decimal_odds": 2.25,
                    }
                ]
            }

        def resolver():
            return PaddyPowerBridgeResolution(
                module_name="fake.module",
                function_name="fake_capture",
                callable=fake_capture,
            )

        rows = fetch_existing_paddy_power_quotes(
            resolver=resolver,
        )

        self.assertEqual(
            len(rows),
            1,
        )
        self.assertEqual(
            rows[0]["fixture_id"],
            9003,
        )

    def test_missing_required_fields_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            _normalise_row(
                {
                    "selection": "Alpha",
                    "decimal_odds": 2.10,
                }
            )


if __name__ == "__main__":
    unittest.main()
