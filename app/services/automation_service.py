from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from time import monotonic
from typing import Callable, Dict, List

from app.models.automation_job_run import AutomationJobRun
from app.services.daily_briefing_service import build_daily_briefing
from app.services.data_provider_service import DataProviderService
from app.services.fixture_import_service import FixtureImportService
from app.services.odds_provider_service import OddsProviderService
from app.services.paddy_power_live_capture import (
    capture_paddy_power_discovered_events_report_once,
)


@dataclass(frozen=True)
class AutomationJob:
    id: str
    name: str
    description: str
    runner: Callable


class AutomationBusyError(RuntimeError):
    pass


class AutomationService:
    _locks: Dict[str, Lock] = {}

    def __init__(self, db):
        self.db = db
        self.jobs = self._build_jobs()
        for job_id in self.jobs:
            self._locks.setdefault(job_id, Lock())

    def _build_jobs(self) -> Dict[str, AutomationJob]:
        return {
            "fixture-import": AutomationJob(
                "fixture-import", "Import fixtures",
                "Import the next seven days from the configured remote fixture provider.",
                self._run_fixture_import,
            ),
            "odds-preview": AutomationJob(
                "odds-preview", "Check odds feed",
                "Validate and preview the configured remote odds provider without storing prices.",
                self._run_odds_preview,
            ),
            "daily-briefing": AutomationJob(
                "daily-briefing", "Refresh daily briefing",
                "Rebuild the daily intelligence briefing from current application data.",
                self._run_daily_briefing,
            ),
            "paddy-power-live": AutomationJob(
                "paddy-power-live", "Capture Paddy Power odds",
                "Capture one live Paddy Power MODUS event-price cycle.",
                self._run_paddy_power_live,
            ),
        }

    def definitions(self) -> List[dict]:
        latest = {row.job_id: row for row in self.latest_runs()}
        return [
            {
                "id": job.id,
                "name": job.name,
                "description": job.description,
                "last_run": latest.get(job.id),
                "running": self._locks[job.id].locked(),
            }
            for job in self.jobs.values()
        ]

    def latest_runs(self, limit: int = 25):
        return (
            self.db.query(AutomationJobRun)
            .order_by(AutomationJobRun.started_at.desc(), AutomationJobRun.id.desc())
            .limit(limit)
            .all()
        )

    def run(self, job_id: str, trigger: str = "manual") -> AutomationJobRun:
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Unknown automation job: {job_id}")
        lock = self._locks[job_id]
        if not lock.acquire(blocking=False):
            raise AutomationBusyError(f"{job.name} is already running")

        started = datetime.utcnow()
        timer = monotonic()
        record = AutomationJobRun(
            job_id=job.id,
            job_name=job.name,
            status="running",
            started_at=started,
            trigger=trigger,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        try:
            processed, detail = job.runner()
            record.status = "success"
            record.records_processed = int(processed or 0)
            record.detail = detail
        except Exception as exc:
            self.db.rollback()
            record = self.db.query(AutomationJobRun).filter(AutomationJobRun.id == record.id).first()
            record.status = "failed"
            record.error = str(exc)
        finally:
            record.finished_at = datetime.utcnow()
            record.duration_seconds = round(monotonic() - timer, 3)
            self.db.commit()
            self.db.refresh(record)
            lock.release()
        return record

    def _run_fixture_import(self):
        provider_service = DataProviderService(self.db)
        report = FixtureImportService(self.db, provider_service).import_fixtures("remote-json", 7)
        return report.created, (
            f"Fetched {report.fetched}; imported {report.created}; "
            f"skipped {report.skipped_duplicates} duplicates; created {report.players_created} players."
        )

    def _run_odds_preview(self):
        service = OddsProviderService()
        provider = service.registry.get("remote-odds-json")
        rows = list(provider.fetch_odds(days=2))
        return len(rows), f"Validated {len(rows)} odds snapshots from the remote feed."

    def _run_paddy_power_live(self):
        report = capture_paddy_power_discovered_events_report_once(
            self.db
        )

        return report.stored_prices, (
            f"Extracted {report.extracted_prices}; "
            f"stored {report.stored_prices}; "
            f"unchanged {report.unchanged_prices}; "
            f"skipped {report.skipped_prices}; "
            f"challenge detected: {report.challenge_detected}."
        )

    def _run_daily_briefing(self):
        briefing = build_daily_briefing(self.db)
        count = briefing["fixture_count"] + briefing["positive_value_count"]
        return count, (
            f"Briefing refreshed with {briefing['fixture_count']} fixtures and "
            f"{briefing['positive_value_count']} confirmed positive-EV opportunities."
        )
