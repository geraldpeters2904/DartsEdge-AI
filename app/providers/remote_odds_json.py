from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.providers.base import DataProvider, OddsRecord, ProviderCapabilities, ProviderHealth


class RemoteJsonOddsProvider(DataProvider):
    provider_id = "remote-odds-json"
    display_name = "Remote JSON odds feed"
    description = "Reads decimal odds from a configurable authorised JSON feed."
    capabilities = ProviderCapabilities(fixtures=False, results=False, odds=True)

    def __init__(self, feed_url: str | None = None, timeout_seconds: int = 12):
        self.feed_url = (feed_url or os.getenv("DARTSEDGE_ODDS_FEED_URL", "")).strip()
        self.timeout_seconds = timeout_seconds

    def health(self) -> ProviderHealth:
        if not self.feed_url:
            return ProviderHealth("disabled", "Set DARTSEDGE_ODDS_FEED_URL to enable remote odds preview.")
        if not self.feed_url.startswith(("https://", "http://", "file://")):
            return ProviderHealth("unhealthy", "Feed URL must use https://, http:// or file://")
        return ProviderHealth("healthy", f"Configured feed: {self.feed_url}")

    def fetch_odds(self, start_date: date, end_date: date) -> Iterable[OddsRecord]:
        if not self.feed_url:
            return []
        payload = self._load_payload()
        raw = payload.get("odds", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw, list):
            raise ValueError("Odds feed must be a JSON list or an object containing an odds list")

        records: list[OddsRecord] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"Odds item {index + 1} must be an object")
            record = self._parse_item(item, index)
            if start_date <= record.event_date <= end_date:
                records.append(record)
        records.sort(key=lambda row: (
            row.event_date,
            row.tournament.casefold(),
            row.player_a.casefold(),
            row.market.casefold(),
            row.selection.casefold(),
            row.bookmaker.casefold(),
        ))
        return records

    def _load_payload(self):
        request = Request(self.feed_url, headers={"User-Agent": "DartsEdgeAI/1.3", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(2_000_000)
        except (URLError, OSError) as exc:
            raise RuntimeError(f"Unable to read odds feed: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Odds feed is not valid UTF-8 JSON: {exc}") from exc

    @staticmethod
    def _parse_item(item: dict, index: int) -> OddsRecord:
        required = ("date", "player_a", "player_b", "bookmaker", "market", "selection", "decimal_odds")
        missing = [key for key in required if item.get(key) in (None, "")]
        if missing:
            raise ValueError(f"Odds item {index + 1} is missing: {', '.join(missing)}")

        event_date = RemoteJsonOddsProvider._parse_date(str(item["date"]))
        player_a = str(item["player_a"]).strip()
        player_b = str(item["player_b"]).strip()
        if not player_a or not player_b or player_a.casefold() == player_b.casefold():
            raise ValueError(f"Odds item {index + 1} must contain two different players")

        try:
            decimal_odds = float(item["decimal_odds"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Odds item {index + 1} has invalid decimal_odds") from exc
        if decimal_odds <= 1.0 or decimal_odds > 1000.0:
            raise ValueError(f"Odds item {index + 1} decimal_odds must be greater than 1.0 and no more than 1000")

        captured_at = RemoteJsonOddsProvider._parse_datetime(item.get("captured_at"))
        known = {"date", "tournament", "player_a", "player_b", "bookmaker", "market", "selection", "decimal_odds", "captured_at", "external_id"}
        return OddsRecord(
            event_date=event_date,
            tournament=str(item.get("tournament") or "Unknown").strip(),
            player_a=player_a,
            player_b=player_b,
            bookmaker=str(item["bookmaker"]).strip(),
            market=str(item["market"]).strip(),
            selection=str(item["selection"]).strip(),
            decimal_odds=decimal_odds,
            captured_at=captured_at,
            external_id=str(item.get("external_id") or "").strip() or None,
            source_metadata={key: value for key, value in item.items() if key not in known},
        )

    @staticmethod
    def _parse_date(value: str) -> date:
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise ValueError(f"Unsupported odds date '{value}'. Use YYYY-MM-DD.") from exc

    @staticmethod
    def _parse_datetime(value) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        cleaned = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError(f"Unsupported captured_at '{value}'. Use ISO-8601.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
