from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

from app.connectors import ConnectorRegistry, FeedConnectorError
from app.models.feed_connector import FeedConnectorConfig, FeedSyncRun
from app.models.match import Match
from app.models.player import Player


class FeedConnectorService:
    DEFAULT_ID = "primary-fixtures"

    def __init__(self, db, registry=None):
        self.db = db
        self.registry = registry or ConnectorRegistry()
        self.ensure_default()

    def ensure_default(self):
        config = self.db.query(FeedConnectorConfig).filter_by(connector_id=self.DEFAULT_ID).first()
        if config:
            return config
        config = FeedConnectorConfig(
            connector_id=self.DEFAULT_ID,
            name="Primary fixture feed",
            connector_type="json",
            enabled=False,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get(self, connector_id=None):
        connector_id = connector_id or self.DEFAULT_ID
        return self.db.query(FeedConnectorConfig).filter_by(connector_id=connector_id).first()

    def save(self, **values):
        config = self.get(values.get("connector_id")) or self.ensure_default()
        config.name = (values.get("name") or config.name).strip()
        config.connector_type = values.get("connector_type") or config.connector_type
        config.feed_url = (values.get("feed_url") or "").strip() or None
        token = values.get("auth_token")
        if token is not None and token != "********":
            config.auth_token = token.strip() or None
        config.enabled = bool(values.get("enabled"))
        competitions = values.get("competitions", "")
        config.competitions_json = json.dumps([x.strip() for x in competitions.split(",") if x.strip()])
        config.timeout_seconds = max(1, min(int(values.get("timeout_seconds", 15)), 60))
        config.retry_count = max(0, min(int(values.get("retry_count", 2)), 5))
        config.refresh_interval_minutes = max(5, min(int(values.get("refresh_interval_minutes", 60)), 1440))
        config.updated_at = datetime.utcnow()
        self.registry.get(config.connector_type)
        self.db.commit()
        self.db.refresh(config)
        return config

    def test_connection(self, connector_id=None):
        config = self.get(connector_id)
        started = time.monotonic()
        health = self.registry.get(config.connector_type).test(config)
        self._history(config.connector_id, "test", health.status, started, error=None if health.status == "healthy" else health.detail)
        return health

    def preview(self, connector_id=None, days=7):
        config = self.get(connector_id)
        started = time.monotonic()
        try:
            records = self.registry.get(config.connector_type).fetch(config)
            records = self._filter(records, config, days)
            existing = self._existing_keys(records)
            rows = [{"fixture": row, "duplicate": row.natural_key() in existing} for row in records]
            self._history(config.connector_id, "preview", "success", started, len(rows), sum(not x["duplicate"] for x in rows), sum(x["duplicate"] for x in rows))
            return {"config": config, "rows": rows, "count": len(rows), "new_count": sum(not x["duplicate"] for x in rows)}
        except Exception as exc:
            self._history(config.connector_id, "preview", "failed", started, error=str(exc))
            raise

    def sync(self, connector_id=None, days=7):
        preview = self.preview(connector_id, days)
        started = time.monotonic()
        created = players_created = skipped = 0
        try:
            for item in preview["rows"]:
                fixture = item["fixture"]
                if item["duplicate"]:
                    skipped += 1
                    continue
                players_created += self._ensure_player(fixture.player_a)
                players_created += self._ensure_player(fixture.player_b)
                self.db.add(Match(date=fixture.event_date, tournament=fixture.tournament, stage=fixture.stage,
                                  match_format=fixture.match_format, status="scheduled", player_a=fixture.player_a,
                                  player_b=fixture.player_b, winner=None, score=None, first_180_player=None,
                                  first_leg_winner=None))
                created += 1
            self.db.commit()
            self._history(preview["config"].connector_id, "sync", "success", started, preview["count"], created, skipped)
            return {"received": preview["count"], "created": created, "existing": skipped, "players_created": players_created}
        except Exception as exc:
            self.db.rollback()
            self._history(preview["config"].connector_id, "sync", "failed", started, preview["count"], created, skipped, error=str(exc))
            raise

    def diagnostics(self):
        config = self.get()
        last = self.db.query(FeedSyncRun).filter_by(connector_id=config.connector_id).order_by(FeedSyncRun.id.desc()).first()
        return {
            "connector": self._serialize(config),
            "registered_types": list(self.registry.types()),
            "last_run": None if not last else self._run_dict(last),
        }

    def history(self, limit=20):
        return self.db.query(FeedSyncRun).order_by(FeedSyncRun.id.desc()).limit(limit).all()

    @staticmethod
    def _serialize(config):
        return {"id": config.connector_id, "name": config.name, "type": config.connector_type,
                "feed_url": config.feed_url, "token_configured": bool(config.auth_token), "enabled": config.enabled,
                "competitions": json.loads(config.competitions_json or "[]"), "timeout_seconds": config.timeout_seconds,
                "retry_count": config.retry_count, "refresh_interval_minutes": config.refresh_interval_minutes}

    @staticmethod
    def _run_dict(run):
        return {"action": run.action, "status": run.status, "started_at": run.started_at.isoformat(),
                "duration_ms": run.duration_ms, "received": run.records_received, "new": run.records_new,
                "existing": run.records_existing, "updated": run.records_updated, "error": run.error_message}

    def _history(self, connector_id, action, status, started, received=0, new=0, existing=0, updated=0, error=None):
        finished = datetime.utcnow()
        run = FeedSyncRun(connector_id=connector_id, action=action, status=status, started_at=finished,
                          finished_at=finished, duration_ms=int((time.monotonic()-started)*1000),
                          records_received=received, records_new=new, records_existing=existing,
                          records_updated=updated, error_message=error)
        self.db.add(run)
        self.db.commit()

    def _filter(self, records, config, days):
        start, end = date.today(), date.today() + timedelta(days=max(0, min(int(days), 31)))
        competitions = {x.casefold() for x in json.loads(config.competitions_json or "[]")}
        return [r for r in records if start <= r.event_date <= end and (not competitions or r.tournament.casefold() in competitions)]

    def _existing_keys(self, records):
        if not records:
            return set()
        start, end = min(r.event_date for r in records), max(r.event_date for r in records)
        matches = self.db.query(Match).filter(Match.date >= start, Match.date <= end).all()
        return {(m.date.isoformat(), (m.tournament or "").strip().casefold(), (m.player_a or "").strip().casefold(), (m.player_b or "").strip().casefold()) for m in matches}

    def _ensure_player(self, name):
        if self.db.query(Player).filter(Player.name == name).first():
            return 0
        self.db.add(Player(name=name)); self.db.flush(); return 1
