from __future__ import annotations

from datetime import date, datetime
from time import perf_counter
from typing import Any, Dict, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.provider_sync import ProviderSyncRun
from app.providers.contracts import CanonicalProviderRecord
from app.providers.registry import ProviderRegistry, provider_registry


VALID_OPERATIONS = {"competitions", "players", "fixtures", "results", "statistics"}


class CollectorService:
    def __init__(self, registry: ProviderRegistry = provider_registry) -> None:
        self.registry = registry

    def run(
        self,
        db: Session,
        provider_id: str,
        operation: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        if operation not in VALID_OPERATIONS:
            raise ValueError(f"Unsupported collector operation '{operation}'")

        provider = self.registry.get(provider_id)
        run = ProviderSyncRun(provider_id=provider_id, operation=operation, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)
        started = perf_counter()

        try:
            health = provider.health()
            if health.status not in {"healthy", "configured"}:
                raise RuntimeError(health.detail)

            method = getattr(provider, operation)
            if operation in {"fixtures", "results", "statistics"}:
                start = start_date or date.today()
                end = end_date or start
                records = method(start, end)
            else:
                records = method()

            records = list(records)
            self._validate_records(provider_id, records)
            run.status = "success"
            run.records_received = len(records)
            run.records_accepted = len(records)
            return {"run_id": run.id, "status": "success", "records": len(records)}
        except Exception as exc:
            run.status = "failed"
            run.error_detail = str(exc)
            return {"run_id": run.id, "status": "failed", "error": str(exc), "records": 0}
        finally:
            run.finished_at = datetime.utcnow()
            run.duration_seconds = round(perf_counter() - started, 6)
            db.commit()

    @staticmethod
    def _validate_records(provider_id: str, records: Sequence[CanonicalProviderRecord]) -> None:
        seen = set()
        for record in records:
            if not isinstance(record, CanonicalProviderRecord):
                raise TypeError(f"Provider '{provider_id}' returned a non-canonical record")
            key = (record.entity_type, record.external_id)
            if key in seen:
                raise ValueError(f"Provider '{provider_id}' returned duplicate record {key}")
            seen.add(key)
