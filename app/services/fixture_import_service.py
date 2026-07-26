from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.models.match import Match
from app.models.player import Player
from app.providers.base import FixtureRecord


@dataclass(frozen=True)
class FixtureImportReport:
    provider_id: str
    fetched: int
    created: int
    skipped_duplicates: int
    players_created: int
    errors: tuple[str, ...]


class FixtureImportService:
    def __init__(self, db, provider_service):
        self.db = db
        self.provider_service = provider_service

    def preview(self, provider_id: str, days: int = 7) -> dict:
        days = max(0, min(int(days), 31))
        start = date.today()
        end = start + timedelta(days=days)
        provider = self.provider_service.registry.get(provider_id)
        fixtures = list(provider.fetch_fixtures(start, end))
        existing = self._existing_keys(start, end)
        rows = []
        for fixture in fixtures:
            rows.append({
                "fixture": fixture,
                "duplicate": fixture.natural_key() in existing,
            })
        return {
            "provider": provider,
            "start_date": start,
            "end_date": end,
            "rows": rows,
            "count": len(rows),
            "new_count": sum(1 for row in rows if not row["duplicate"]),
        }

    def import_fixtures(self, provider_id: str, days: int = 7) -> FixtureImportReport:
        preview = self.preview(provider_id, days)
        created = 0
        skipped = 0
        players_created = 0
        errors: list[str] = []

        try:
            for row in preview["rows"]:
                fixture: FixtureRecord = row["fixture"]
                if row["duplicate"]:
                    skipped += 1
                    continue
                try:
                    players_created += self._ensure_player(fixture.player_a)
                    players_created += self._ensure_player(fixture.player_b)
                    self.db.add(Match(
                        date=fixture.event_date,
                        tournament=fixture.tournament,
                        stage=fixture.stage,
                        match_format=fixture.match_format,
                        status="scheduled",
                        player_a=fixture.player_a,
                        player_b=fixture.player_b,
                        winner=None,
                        score=None,
                        first_180_player=None,
                        first_leg_winner=None,
                    ))
                    created += 1
                except Exception as exc:  # defensive per-record reporting
                    errors.append(f"{fixture.player_a} vs {fixture.player_b}: {exc}")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return FixtureImportReport(
            provider_id=provider_id,
            fetched=preview["count"],
            created=created,
            skipped_duplicates=skipped,
            players_created=players_created,
            errors=tuple(errors),
        )

    def _ensure_player(self, player_name: str) -> int:
        existing = self.db.query(Player).filter(Player.name == player_name).first()
        if existing:
            return 0
        self.db.add(Player(name=player_name))
        self.db.flush()
        return 1

    def _existing_keys(self, start: date, end: date) -> set[tuple[str, str, str, str]]:
        rows = self.db.query(Match).filter(Match.date >= start, Match.date <= end).all()
        return {
            (
                row.date.isoformat(),
                (row.tournament or "").strip().casefold(),
                (row.player_a or "").strip().casefold(),
                (row.player_b or "").strip().casefold(),
            )
            for row in rows
        }
