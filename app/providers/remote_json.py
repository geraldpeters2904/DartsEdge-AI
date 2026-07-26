from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.providers.base import DataProvider, FixtureRecord, ProviderCapabilities, ProviderHealth


class RemoteJsonFixtureProvider(DataProvider):
    provider_id = "remote-json"
    display_name = "Remote JSON fixture feed"
    description = "Imports fixtures from a configurable HTTPS JSON feed."
    capabilities = ProviderCapabilities(fixtures=True, results=False, odds=False)

    def __init__(self, feed_url: str | None = None, timeout_seconds: int = 12):
        self.feed_url = (feed_url or os.getenv("DARTSEDGE_FIXTURE_FEED_URL", "")).strip()
        self.timeout_seconds = timeout_seconds

    def health(self) -> ProviderHealth:
        if not self.feed_url:
            return ProviderHealth(
                "disabled",
                "Set DARTSEDGE_FIXTURE_FEED_URL to enable remote fixture imports.",
            )
        if not self.feed_url.startswith(("https://", "http://", "file://")):
            return ProviderHealth("unhealthy", "Feed URL must use https://, http:// or file://")
        return ProviderHealth("healthy", f"Configured feed: {self.feed_url}")

    def fetch_fixtures(self, start_date: date, end_date: date) -> Iterable[FixtureRecord]:
        if not self.feed_url:
            return []
        payload = self._load_payload()
        raw_fixtures = payload.get("fixtures", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_fixtures, list):
            raise ValueError("Fixture feed must be a JSON list or an object containing a fixtures list")

        fixtures: list[FixtureRecord] = []
        for index, item in enumerate(raw_fixtures):
            if not isinstance(item, dict):
                raise ValueError(f"Fixture item {index + 1} must be an object")
            record = self._parse_fixture(item, index)
            if start_date <= record.event_date <= end_date:
                fixtures.append(record)
        fixtures.sort(key=lambda f: (f.event_date, f.tournament.casefold(), f.player_a.casefold()))
        return fixtures

    def _load_payload(self):
        request = Request(
            self.feed_url,
            headers={"User-Agent": "DartsEdgeAI/1.3", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(2_000_000)
        except (URLError, OSError) as exc:
            raise RuntimeError(f"Unable to read fixture feed: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Fixture feed is not valid UTF-8 JSON: {exc}") from exc

    @staticmethod
    def _parse_fixture(item: dict, index: int) -> FixtureRecord:
        required = ("date", "player_a", "player_b")
        missing = [key for key in required if not str(item.get(key, "")).strip()]
        if missing:
            raise ValueError(f"Fixture item {index + 1} is missing: {', '.join(missing)}")
        event_date = RemoteJsonFixtureProvider._parse_date(str(item["date"]))
        player_a = str(item["player_a"]).strip()
        player_b = str(item["player_b"]).strip()
        if player_a.casefold() == player_b.casefold():
            raise ValueError(f"Fixture item {index + 1} has the same player on both sides")
        return FixtureRecord(
            event_date=event_date,
            tournament=str(item.get("tournament") or "Unknown").strip(),
            stage=str(item.get("stage") or "Unknown").strip(),
            match_format=str(item.get("match_format") or "Best of 7").strip(),
            player_a=player_a,
            player_b=player_b,
            external_id=str(item.get("external_id") or "").strip() or None,
            source_metadata={
                key: value for key, value in item.items()
                if key not in {"date", "tournament", "stage", "match_format", "player_a", "player_b", "external_id"}
            },
        )

    @staticmethod
    def _parse_date(value: str) -> date:
        cleaned = value.strip()
        try:
            return date.fromisoformat(cleaned[:10])
        except ValueError:
            try:
                return datetime.strptime(cleaned, "%d/%m/%Y").date()
            except ValueError as exc:
                raise ValueError(f"Unsupported fixture date '{value}'. Use YYYY-MM-DD.") from exc
