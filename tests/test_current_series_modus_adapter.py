import unittest
from datetime import date
from types import SimpleNamespace

from app.services.current_series_modus_adapter import (
    build_current_series_fetcher,
)


class CurrentSeriesModusAdapterTests(
    unittest.TestCase
):
    def test_adapts_match_like_rows(self):
        def fetch(
            start,
            end,
        ):
            return [
                SimpleNamespace(
                    date=date(
                        2026,
                        8,
                        7,
                    ),
                    tournament="MODUS",
                    player_a="Alpha",
                    player_b="Bravo",
                    status="scheduled",
                    stage="Group A",
                    match_format="Best of 7",
                    winner=None,
                    score_a=None,
                    score_b=None,
                    provider_id="123",
                )
            ]

        adapter = (
            build_current_series_fetcher(
                fetch_matches=fetch,
            )
        )

        rows = adapter(
            date(
                2026,
                8,
                1,
            ),
            date(
                2026,
                8,
                14,
            ),
        )

        self.assertEqual(
            len(
                rows
            ),
            1,
        )

        row = rows[0]

        self.assertEqual(
            row.player_a,
            "Alpha",
        )

        self.assertEqual(
            row.player_b,
            "Bravo",
        )

        self.assertEqual(
            row.status,
            "scheduled",
        )

        self.assertEqual(
            row.provider_id,
            "123",
        )

    def test_completed_rows_preserve_result(self):
        def fetch(
            start,
            end,
        ):
            return [
                SimpleNamespace(
                    date=date(
                        2026,
                        8,
                        7,
                    ),
                    tournament="MODUS",
                    player_a="Alpha",
                    player_b="Bravo",
                    status="completed",
                    stage="Group A",
                    match_format="Best of 7",
                    winner="Alpha",
                    score_a=4,
                    score_b=2,
                    provider_id="123",
                )
            ]

        adapter = (
            build_current_series_fetcher(
                fetch_matches=fetch,
            )
        )

        row = adapter(
            date(
                2026,
                8,
                1,
            ),
            date(
                2026,
                8,
                14,
            ),
        )[0]

        self.assertEqual(
            row.status,
            "completed",
        )

        self.assertEqual(
            row.winner,
            "Alpha",
        )

        self.assertEqual(
            row.score_a,
            4,
        )

        self.assertEqual(
            row.score_b,
            2,
        )


if __name__ == "__main__":
    unittest.main()
