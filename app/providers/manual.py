from __future__ import annotations

from datetime import date
from typing import Iterable

from app.models.match import Match
from app.providers.base import (
    DataProvider,
    FixtureRecord,
    ProviderCapabilities,
    ProviderHealth,
)


class ManualDatabaseProvider(DataProvider):
    provider_id = "manual"
    display_name = "Manual database"
    description = "Fixtures entered directly in DartsEdge AI."
    capabilities = ProviderCapabilities(fixtures=True, results=True, odds=False)

    def __init__(self, db):
        self.db = db

    def health(self) -> ProviderHealth:
        try:
            self.db.query(Match.id).limit(1).all()
            return ProviderHealth("healthy", "Database fixture storage is available")
        except Exception as exc:  # pragma: no cover - defensive runtime diagnostic
            return ProviderHealth("unhealthy", f"Database fixture storage failed: {exc}")

    def fetch_fixtures(self, start_date: date, end_date: date) -> Iterable[FixtureRecord]:
        rows = (
            self.db.query(Match)
            .filter(Match.date >= start_date, Match.date <= end_date)
            .order_by(Match.date.asc(), Match.id.asc())
            .all()
        )
        return [
            FixtureRecord(
                event_date=row.date,
                tournament=row.tournament or "Unknown",
                stage=row.stage or "Unknown",
                match_format=row.match_format or "Unknown",
                player_a=row.player_a,
                player_b=row.player_b,
                external_id=f"manual:{row.id}",
                source_metadata={"status": row.status, "database_id": row.id},
            )
            for row in rows
        ]
