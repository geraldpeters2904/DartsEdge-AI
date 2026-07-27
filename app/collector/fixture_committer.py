from __future__ import annotations

from typing import List

from app.models.historical_import import HistoricalImportBatch
from app.schemas.canonical import CanonicalFixture
from app.services.historical_import_service import import_rows


class FixtureCommitter:
    """
    Commits canonical fixture records using the existing
    historical import pipeline.
    """

    def commit(
        self,
        *,
        db,
        provider: str,
        filename: str,
        competition: str,
        fixtures: List[CanonicalFixture],
    ) -> HistoricalImportBatch:

        rows = [
            self._to_historical_row(fixture)
            for fixture in fixtures
        ]

        return import_rows(
            db,
            rows,
            filename=filename,
            provider=provider,
            competition=competition,
        )

    @staticmethod
    def _to_historical_row(
        fixture: CanonicalFixture,
    ) -> dict:

        return {
            "external_id": fixture.external_id,
            "date": fixture.scheduled_at.date(),
            "competition": fixture.competition_code.value,
            "tournament": fixture.competition_name,
            "stage": fixture.stage or "Scheduled",
            "match_format": fixture.match_format,
            "status": fixture.status.value,
            "player_a": fixture.player_a_name,
            "player_b": fixture.player_b_name,
            "winner": None,
            "score": None,
            "first_180_player": None,
            "first_leg_winner": None,
            "provider": fixture.source.provider,
            "player_a_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
            "player_b_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
        }