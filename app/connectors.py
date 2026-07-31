from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.providers.base import FixtureRecord


@dataclass(frozen=True)
class ConnectorHealth:
    status: str
    detail: str


class FeedConnectorError(ValueError):
    pass


class BaseFeedConnector:
    connector_type = "base"

    def fetch(self, config) -> list[FixtureRecord]:
        raise NotImplementedError

    def test(self, config) -> ConnectorHealth:
        try:
            records = self.fetch(config)
            return ConnectorHealth("healthy", f"Connection succeeded; {len(records)} fixture records available")
        except FeedConnectorError as exc:
            return ConnectorHealth("unhealthy", str(exc))

    @staticmethod
    def _request_text(config) -> str:
        if not config.enabled:
            raise FeedConnectorError("Connector is disabled")
        if not (config.feed_url or "").strip():
            raise FeedConnectorError("Feed URL is required")
        headers = {"Accept": "application/json, text/csv;q=0.9, */*;q=0.1"}
        if config.auth_token:
            headers["Authorization"] = f"Bearer {config.auth_token}"
        request = Request(config.feed_url.strip(), headers=headers)
        try:
            with urlopen(request, timeout=max(1, min(config.timeout_seconds, 60))) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            raise FeedConnectorError(f"Feed returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise FeedConnectorError(f"Could not reach feed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise FeedConnectorError("Feed request timed out") from exc

    @staticmethod
    def _fixture(item: dict) -> FixtureRecord:
        required = ("date", "tournament", "player_a", "player_b")
        missing = [key for key in required if not str(item.get(key, "")).strip()]
        if missing:
            raise FeedConnectorError("Fixture is missing: " + ", ".join(missing))
        try:
            event_date = date.fromisoformat(str(item["date"])[:10])
        except ValueError as exc:
            raise FeedConnectorError(f"Invalid fixture date: {item.get('date')}") from exc
        return FixtureRecord(
            event_date=event_date,
            tournament=str(item["tournament"]).strip(),
            player_a=str(item["player_a"]).strip(),
            player_b=str(item["player_b"]).strip(),
            stage=str(item.get("stage") or "").strip() or None,
            match_format=str(item.get("match_format") or "").strip() or None,
        )


class JsonFeedConnector(BaseFeedConnector):
    connector_type = "json"

    def fetch(self, config) -> list[FixtureRecord]:
        text = self._request_text(config)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise FeedConnectorError("Feed did not return valid JSON") from exc
        if isinstance(payload, dict):
            payload = payload.get("fixtures", payload.get("data"))
        if not isinstance(payload, list):
            raise FeedConnectorError("JSON feed must contain a fixture list or a fixtures/data list")
        return [self._fixture(item) for item in payload]


class CsvFeedConnector(BaseFeedConnector):
    connector_type = "csv"

    def fetch(self, config) -> list[FixtureRecord]:
        text = self._request_text(config)
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except csv.Error as exc:
            raise FeedConnectorError("Feed did not return valid CSV") from exc
        if not rows:
            return []
        return [self._fixture(row) for row in rows]


class ConnectorRegistry:
    def __init__(self):
        self._types = {}
        self.register(JsonFeedConnector())
        self.register(CsvFeedConnector())

    def register(self, connector: BaseFeedConnector):
        if connector.connector_type in self._types:
            raise ValueError(f"Connector type already registered: {connector.connector_type}")
        self._types[connector.connector_type] = connector

    def get(self, connector_type: str) -> BaseFeedConnector:
        try:
            return self._types[connector_type]
        except KeyError as exc:
            raise FeedConnectorError(f"Unsupported connector type: {connector_type}") from exc

    def types(self):
        return tuple(sorted(self._types))
