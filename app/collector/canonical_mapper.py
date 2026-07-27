from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional

from pydantic import BaseModel, ValidationError

from app.collector.csv_definitions import (
    CSV_REQUIRED_HEADERS,
    allowed_headers,
)
from app.collector.csv_parser import (
    CanonicalCsvParser,
    CsvParseIssue,
    CsvParseResult,
)
from app.schemas.canonical import (
    CanonicalFixture,
    CanonicalMatchResult,
    CanonicalOddsSnapshot,
    CanonicalPlayerMatchStatistics,
)
from app.services.import_session_service import (
    ImportSessionResult,
    build_import_session,
)


SCHEMAS = {
    "fixtures": CanonicalFixture,
    "results": CanonicalMatchResult,
    "statistics": CanonicalPlayerMatchStatistics,
    "odds": CanonicalOddsSnapshot,
}

INTEGER_FIELDS = {
    "player_a_legs",
    "player_b_legs",
    "scores_100_plus",
    "scores_140_plus",
    "scores_180",
    "checkout_attempts",
    "checkouts_completed",
    "highest_checkout",
    "legs_won",
    "legs_lost",
    "legs_held",
    "legs_broken",
    "match_duration_seconds",
}

FLOAT_FIELDS = {
    "three_dart_average",
    "first_nine_average",
    "checkout_percentage",
    "decimal_odds",
}

DATETIME_FIELDS = {
    "scheduled_at",
    "actual_start_at",
    "completed_at",
    "captured_at",
    "source_retrieved_at",
}


class CanonicalCsvMappingResult:
    def __init__(
        self,
        *,
        entity_type: str,
        parse_result: CsvParseResult,
        records: List[BaseModel],
        issues: List[CsvParseIssue],
    ):
        self.entity_type = entity_type
        self.parse_result = parse_result
        self.records = records
        self.issues = issues

    @property
    def error_count(self) -> int:
        return sum(
            1 for issue in self.issues
            if issue.severity == "error"
        )

    @property
    def valid(self) -> bool:
        return self.parse_result.valid and self.error_count == 0


class CanonicalCsvMapper:
    """Convert parsed CSV rows into canonical Pydantic records."""

    def __init__(self):
        self.parser = CanonicalCsvParser()

    def map_text(
        self,
        *,
        entity_type: str,
        csv_text: str,
        provider: str,
        filename: str = "<memory>",
        retrieved_at: Optional[datetime] = None,
    ) -> CanonicalCsvMappingResult:
        if entity_type not in SCHEMAS:
            raise ValueError(
                f"Unsupported CSV entity type: {entity_type}"
            )

        parsed = self.parser.parse_text(
            csv_text,
            filename=filename,
            required_headers=CSV_REQUIRED_HEADERS[entity_type],
            allowed_headers=allowed_headers(entity_type),
        )

        issues = list(parsed.issues)
        canonical_records: List[BaseModel] = []

        if not parsed.valid:
            return CanonicalCsvMappingResult(
                entity_type=entity_type,
                parse_result=parsed,
                records=[],
                issues=issues,
            )

        schema = SCHEMAS[entity_type]

        for index, row in enumerate(parsed.records, start=2):
            try:
                payload = self._build_payload(
                    entity_type=entity_type,
                    row=row,
                    provider=provider,
                    retrieved_at=retrieved_at,
                )
                canonical_records.append(
                    schema.model_validate(payload)
                )
            except (ValueError, ValidationError) as exc:
                issues.append(
                    CsvParseIssue(
                        severity="error",
                        code="canonical_validation",
                        message=str(exc),
                        row_number=index,
                    )
                )

        return CanonicalCsvMappingResult(
            entity_type=entity_type,
            parse_result=parsed,
            records=canonical_records,
            issues=issues,
        )

    def preview_texts(
        self,
        *,
        provider: str,
        csv_by_type: Mapping[str, str],
        retrieved_at: Optional[datetime] = None,
    ) -> tuple[
        Dict[str, CanonicalCsvMappingResult],
        ImportSessionResult,
    ]:
        mappings: Dict[str, CanonicalCsvMappingResult] = {}
        records_by_type: Dict[str, Iterable[BaseModel]] = {}

        for entity_type, csv_text in csv_by_type.items():
            mapping = self.map_text(
                entity_type=entity_type,
                csv_text=csv_text,
                provider=provider,
                filename=f"{entity_type}.csv",
                retrieved_at=retrieved_at,
            )
            mappings[entity_type] = mapping

            if mapping.valid:
                records_by_type[entity_type] = mapping.records

        session = build_import_session(
            provider=provider,
            records_by_type=records_by_type,
            dry_run=True,
        )

        return mappings, session

    def _build_payload(
        self,
        *,
        entity_type: str,
        row: Mapping[str, Optional[str]],
        provider: str,
        retrieved_at: Optional[datetime],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        for field_name, raw_value in row.items():
            if field_name.startswith("source_"):
                continue

            if field_name in INTEGER_FIELDS:
                payload[field_name] = self._integer(
                    raw_value,
                    field_name,
                )
            elif field_name in FLOAT_FIELDS:
                payload[field_name] = self._float(
                    raw_value,
                    field_name,
                )
            elif field_name in DATETIME_FIELDS:
                payload[field_name] = self._datetime(
                    raw_value,
                    field_name,
                )
            else:
                payload[field_name] = raw_value

        source_provider = (
            row.get("source_provider")
            or provider.strip()
        )
        if not source_provider:
            raise ValueError("Source provider must not be blank.")

        source_external_id = (
            row.get("source_external_id")
            or self._default_source_id(entity_type, payload)
        )
        if not source_external_id:
            raise ValueError(
                "Unable to determine source_external_id."
            )

        source_retrieved_at = self._datetime(
            row.get("source_retrieved_at"),
            "source_retrieved_at",
        ) or retrieved_at or datetime.utcnow()

        payload["source"] = {
            "provider": source_provider,
            "external_id": source_external_id,
            "retrieved_at": source_retrieved_at,
            "competition_code": (
                row.get("source_competition_code")
                or payload.get("competition_code")
            ),
            "confidence": (
                row.get("source_confidence")
                or "reported"
            ),
        }

        return payload

    @staticmethod
    def _default_source_id(
        entity_type: str,
        payload: Mapping[str, Any],
    ) -> Optional[str]:
        if entity_type == "fixtures":
            return payload.get("external_id")

        if entity_type == "results":
            return payload.get("match_external_id")

        if entity_type == "statistics":
            match_id = payload.get("match_external_id")
            player_id = payload.get("player_external_id")
            if match_id and player_id:
                return f"{match_id}:{player_id}"

        if entity_type == "odds":
            parts = (
                payload.get("match_external_id"),
                payload.get("bookmaker"),
                payload.get("market"),
                payload.get("selection_external_id")
                or payload.get("selection_name"),
            )
            if all(parts):
                return ":".join(str(part) for part in parts)

        return None

    @staticmethod
    def _integer(
        value: Optional[str],
        field_name: str,
    ) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be an integer."
            ) from exc

    @staticmethod
    def _float(
        value: Optional[str],
        field_name: str,
    ) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

    @staticmethod
    def _datetime(
        value: Optional[str],
        field_name: str,
    ) -> Optional[datetime]:
        if value is None:
            return None

        candidate = value
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"

        try:
            return datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must use ISO-8601 format."
            ) from exc
