from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Type

from pydantic import BaseModel, ValidationError

from app.schemas.canonical import (
    CanonicalCompetition,
    CanonicalFixture,
    CanonicalMatchResult,
    CanonicalOddsSnapshot,
    CanonicalPlayer,
    CanonicalPlayerMatchStatistics,
)


CANONICAL_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "players": CanonicalPlayer,
    "competitions": CanonicalCompetition,
    "fixtures": CanonicalFixture,
    "results": CanonicalMatchResult,
    "statistics": CanonicalPlayerMatchStatistics,
    "odds": CanonicalOddsSnapshot,
}


@dataclass(frozen=True)
class ImportIssue:
    """One validation, duplicate or quality issue discovered in a session."""

    severity: str
    code: str
    message: str
    entity_type: Optional[str] = None
    record_index: Optional[int] = None
    field_name: Optional[str] = None


@dataclass
class ImportEntitySummary:
    """Validation totals for one canonical entity type."""

    received: int = 0
    valid: int = 0
    rejected: int = 0
    duplicates: int = 0


@dataclass
class ImportSessionResult:
    """
    Provider-independent result of validating an import payload.

    This object contains no SQLAlchemy session and performs no database writes.
    """

    provider: str
    dry_run: bool
    validated_records: Dict[str, List[BaseModel]] = field(default_factory=dict)
    entity_summaries: Dict[str, ImportEntitySummary] = field(default_factory=dict)
    issues: List[ImportIssue] = field(default_factory=list)
    quality_score: float = 0.0
    ready_to_commit: bool = False

    @property
    def total_received(self) -> int:
        return sum(item.received for item in self.entity_summaries.values())

    @property
    def total_valid(self) -> int:
        return sum(item.valid for item in self.entity_summaries.values())

    @property
    def total_rejected(self) -> int:
        return sum(item.rejected for item in self.entity_summaries.values())

    @property
    def total_duplicates(self) -> int:
        return sum(item.duplicates for item in self.entity_summaries.values())

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "dry_run": self.dry_run,
            "quality_score": self.quality_score,
            "ready_to_commit": self.ready_to_commit,
            "totals": {
                "received": self.total_received,
                "valid": self.total_valid,
                "rejected": self.total_rejected,
                "duplicates": self.total_duplicates,
                "errors": self.error_count,
                "warnings": self.warning_count,
            },
            "entities": {
                name: {
                    "received": summary.received,
                    "valid": summary.valid,
                    "rejected": summary.rejected,
                    "duplicates": summary.duplicates,
                }
                for name, summary in self.entity_summaries.items()
            },
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "entity_type": issue.entity_type,
                    "record_index": issue.record_index,
                    "field_name": issue.field_name,
                }
                for issue in self.issues
            ],
        }


class ImportSessionService:
    """
    Validates mixed canonical records before a future commit stage.

    Input format:

        {
            "fixtures": [{...}, {...}],
            "results": [{...}],
            "statistics": [{...}],
        }

    Records can be dictionaries or already-validated Pydantic models.
    """

    def validate(
        self,
        provider: str,
        records_by_type: Mapping[str, Iterable[Any]],
        *,
        dry_run: bool = True,
    ) -> ImportSessionResult:
        provider = provider.strip()

        if not provider:
            raise ValueError("provider must not be blank")

        result = ImportSessionResult(
            provider=provider,
            dry_run=dry_run,
            validated_records={},
            entity_summaries={},
        )

        for entity_type, raw_records in records_by_type.items():
            if entity_type not in CANONICAL_SCHEMA_REGISTRY:
                result.issues.append(
                    ImportIssue(
                        severity="error",
                        code="unsupported_entity_type",
                        message=f"Unsupported canonical entity type: {entity_type}",
                        entity_type=entity_type,
                    )
                )
                continue

            schema = CANONICAL_SCHEMA_REGISTRY[entity_type]
            records = list(raw_records)
            summary = ImportEntitySummary(received=len(records))
            valid_records: List[BaseModel] = []
            seen_keys = set()

            for index, raw_record in enumerate(records):
                try:
                    canonical_record = self._validate_record(schema, raw_record)
                except ValidationError as exc:
                    summary.rejected += 1
                    self._append_validation_issues(
                        result=result,
                        entity_type=entity_type,
                        record_index=index,
                        error=exc,
                    )
                    continue
                except (TypeError, ValueError) as exc:
                    summary.rejected += 1
                    result.issues.append(
                        ImportIssue(
                            severity="error",
                            code="invalid_record",
                            message=str(exc),
                            entity_type=entity_type,
                            record_index=index,
                        )
                    )
                    continue

                duplicate_key = self._duplicate_key(
                    entity_type,
                    canonical_record,
                )

                if duplicate_key in seen_keys:
                    summary.duplicates += 1
                    result.issues.append(
                        ImportIssue(
                            severity="warning",
                            code="duplicate_in_session",
                            message=(
                                "Duplicate canonical record found within the "
                                "same import session."
                            ),
                            entity_type=entity_type,
                            record_index=index,
                        )
                    )
                    continue

                seen_keys.add(duplicate_key)
                valid_records.append(canonical_record)
                summary.valid += 1

            result.entity_summaries[entity_type] = summary
            result.validated_records[entity_type] = valid_records

        result.quality_score = self._calculate_quality_score(result)
        result.ready_to_commit = (
            result.total_valid > 0
            and result.error_count == 0
            and result.total_rejected == 0
        )

        return result

    @staticmethod
    def _validate_record(
        schema: Type[BaseModel],
        raw_record: Any,
    ) -> BaseModel:
        if isinstance(raw_record, schema):
            return raw_record

        if isinstance(raw_record, BaseModel):
            return schema.model_validate(raw_record.model_dump())

        if isinstance(raw_record, Mapping):
            return schema.model_validate(dict(raw_record))

        raise TypeError(
            "Import records must be dictionaries or Pydantic models."
        )

    @staticmethod
    def _append_validation_issues(
        *,
        result: ImportSessionResult,
        entity_type: str,
        record_index: int,
        error: ValidationError,
    ) -> None:
        for item in error.errors():
            location = item.get("loc", ())
            field_name = ".".join(str(part) for part in location) or None
            message = item.get("msg", "Validation failed")

            result.issues.append(
                ImportIssue(
                    severity="error",
                    code="schema_validation",
                    message=message,
                    entity_type=entity_type,
                    record_index=record_index,
                    field_name=field_name,
                )
            )

    @staticmethod
    def _duplicate_key(
        entity_type: str,
        record: BaseModel,
    ) -> Tuple[Any, ...]:
        data = record.model_dump()

        if entity_type in {"players", "competitions", "fixtures"}:
            source = data.get("source") or {}
            return (
                entity_type,
                source.get("provider"),
                data.get("external_id"),
            )

        if entity_type == "results":
            source = data.get("source") or {}
            return (
                entity_type,
                source.get("provider"),
                data.get("match_external_id"),
            )

        if entity_type == "statistics":
            source = data.get("source") or {}
            return (
                entity_type,
                source.get("provider"),
                data.get("match_external_id"),
                data.get("player_external_id"),
            )

        if entity_type == "odds":
            source = data.get("source") or {}
            return (
                entity_type,
                source.get("provider"),
                data.get("match_external_id"),
                data.get("market"),
                data.get("selection_external_id"),
                data.get("selection_name"),
                data.get("bookmaker"),
                data.get("captured_at"),
            )

        return entity_type, repr(data)

    @staticmethod
    def _calculate_quality_score(result: ImportSessionResult) -> float:
        if result.total_received == 0:
            return 0.0

        valid_ratio = result.total_valid / result.total_received
        base_score = valid_ratio * 100.0

        warning_penalty = min(15.0, result.warning_count * 2.0)
        error_penalty = min(40.0, result.error_count * 5.0)

        return round(
            max(0.0, base_score - warning_penalty - error_penalty),
            1,
        )


def build_import_session(
    provider: str,
    records_by_type: Mapping[str, Iterable[Any]],
    *,
    dry_run: bool = True,
) -> ImportSessionResult:
    """Convenience entry point for routes, jobs and provider adapters."""

    return ImportSessionService().validate(
        provider=provider,
        records_by_type=records_by_type,
        dry_run=dry_run,
    )
