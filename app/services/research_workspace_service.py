from __future__ import annotations

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Optional

from app.collector.csv_definitions import (
    CSV_OPTIONAL_HEADERS,
    CSV_REQUIRED_HEADERS,
    CSV_SOURCE_HEADERS,
)
from app.models.historical_import import HistoricalImportPreview


ENTITY_TYPES = ("fixtures", "results", "statistics", "odds")

HEADER_ALIASES: Dict[str, Dict[str, str]] = {
    "fixtures": {
        "match_id": "external_id",
        "fixture_id": "external_id",
        "event_id": "external_id",
        "competition": "competition_name",
        "tournament": "competition_name",
        "date_time": "scheduled_at",
        "datetime": "scheduled_at",
        "start_time": "scheduled_at",
        "scheduled": "scheduled_at",
        "player_1": "player_a_name",
        "player1": "player_a_name",
        "home_player": "player_a_name",
        "player_a": "player_a_name",
        "player_2": "player_b_name",
        "player2": "player_b_name",
        "away_player": "player_b_name",
        "player_b": "player_b_name",
        "format": "match_format",
        "round": "stage",
    },
    "results": {
        "match_id": "match_external_id",
        "fixture_id": "match_external_id",
        "player_1": "player_a_external_id",
        "player1": "player_a_external_id",
        "player_a": "player_a_external_id",
        "player_2": "player_b_external_id",
        "player2": "player_b_external_id",
        "player_b": "player_b_external_id",
        "winner": "winner_external_id",
        "player_1_legs": "player_a_legs",
        "player1_legs": "player_a_legs",
        "player_a_score": "player_a_legs",
        "player_2_legs": "player_b_legs",
        "player2_legs": "player_b_legs",
        "player_b_score": "player_b_legs",
        "finished_at": "completed_at",
    },
    "statistics": {
        "match_id": "match_external_id",
        "fixture_id": "match_external_id",
        "player_id": "player_external_id",
        "player": "player_external_id",
        "average": "three_dart_average",
        "avg": "three_dart_average",
        "3_dart_average": "three_dart_average",
        "first_9_average": "first_nine_average",
        "first9": "first_nine_average",
        "100_plus": "scores_100_plus",
        "140_plus": "scores_140_plus",
        "180s": "scores_180",
        "180": "scores_180",
        "checkout_pct": "checkout_percentage",
        "checkout_percent": "checkout_percentage",
        "highest_finish": "highest_checkout",
    },
    "odds": {
        "match_id": "match_external_id",
        "fixture_id": "match_external_id",
        "selection": "selection_name",
        "player": "selection_name",
        "bookie": "bookmaker",
        "price": "decimal_odds",
        "odds": "decimal_odds",
        "timestamp": "captured_at",
        "time": "captured_at",
    },
}


@dataclass(frozen=True)
class ParsedTable:
    headers: List[str]
    rows: List[List[str]]
    delimiter: str


def normalise_header(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return text.strip("_")


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return text.strip("-") or "unknown"


class ResearchWorkspaceService:
    """Paste-table research sessions that produce canonical CSV text."""

    def parse_table(self, raw_text: str) -> ParsedTable:
        raw_text = raw_text.strip("\ufeff\n\r ")
        if not raw_text:
            raise ValueError("Paste at least one header row and one data row.")

        sample = raw_text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters="\t,;")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = "\t" if "\t" in sample else ","

        reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
        rows = [[cell.strip() for cell in row] for row in reader if any(cell.strip() for cell in row)]
        if len(rows) < 2:
            raise ValueError("The pasted table must contain a header row and at least one data row.")

        width = len(rows[0])
        if width == 0:
            raise ValueError("The pasted table has no columns.")
        if any(len(row) != width for row in rows[1:]):
            raise ValueError("Every pasted row must contain the same number of columns.")

        return ParsedTable(headers=rows[0], rows=rows[1:], delimiter=delimiter)

    def suggested_mapping(self, entity_type: str, headers: Iterable[str]) -> Dict[str, str]:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"Unsupported research entity type: {entity_type}")

        allowed = set(
            CSV_REQUIRED_HEADERS[entity_type]
            + CSV_OPTIONAL_HEADERS[entity_type]
            + CSV_SOURCE_HEADERS
        )
        aliases = HEADER_ALIASES[entity_type]
        mapping: Dict[str, str] = {}

        for header in headers:
            normalised = normalise_header(header)
            if normalised in allowed:
                mapping[header] = normalised
            elif normalised in aliases:
                mapping[header] = aliases[normalised]
            else:
                mapping[header] = ""
        return mapping

    def build_canonical_csv(
        self,
        *,
        entity_type: str,
        table: ParsedTable,
        mapping: Mapping[str, str],
        provider: str,
        competition: str,
    ) -> str:
        if entity_type not in ENTITY_TYPES:
            raise ValueError(f"Unsupported research entity type: {entity_type}")

        provider = provider.strip()
        competition = competition.strip().upper()
        if not provider:
            raise ValueError("Provider must not be blank.")
        if not competition:
            raise ValueError("Competition must not be blank.")

        selected = [mapping.get(header, "") for header in table.headers]
        duplicates = {name for name in selected if name and selected.count(name) > 1}
        if duplicates:
            raise ValueError("Each canonical field can only be mapped once: " + ", ".join(sorted(duplicates)))

        mapped_fields = {name for name in selected if name}
        missing = [name for name in CSV_REQUIRED_HEADERS[entity_type] if name not in mapped_fields]
        if missing:
            raise ValueError("Required canonical fields are not mapped: " + ", ".join(missing))

        output_headers = [name for name in (
            CSV_REQUIRED_HEADERS[entity_type]
            + CSV_OPTIONAL_HEADERS[entity_type]
            + CSV_SOURCE_HEADERS
        ) if name in mapped_fields or name in CSV_SOURCE_HEADERS]

        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=output_headers, lineterminator="\n")
        writer.writeheader()
        retrieved_at = datetime.utcnow().replace(microsecond=0).isoformat()

        for index, values in enumerate(table.rows, start=1):
            row: Dict[str, str] = {}
            for header, value in zip(table.headers, values):
                field = mapping.get(header, "")
                if field:
                    row[field] = self._normalise_value(field, value)

            row["source_provider"] = provider
            row["source_external_id"] = row.get("source_external_id") or self._source_id(entity_type, row, index)
            row["source_retrieved_at"] = row.get("source_retrieved_at") or retrieved_at
            row["source_competition_code"] = row.get("source_competition_code") or competition
            row["source_confidence"] = row.get("source_confidence") or "manual"
            writer.writerow({name: row.get(name, "") for name in output_headers})

        return stream.getvalue()

    def create_session(
        self,
        *,
        db,
        entity_type: str,
        raw_text: str,
        provider: str,
        competition: str,
        mapping: Optional[Mapping[str, str]] = None,
    ) -> HistoricalImportPreview:
        table = self.parse_table(raw_text)
        mapping = dict(mapping or self.suggested_mapping(entity_type, table.headers))
        canonical_csv = self.build_canonical_csv(
            entity_type=entity_type,
            table=table,
            mapping=mapping,
            provider=provider,
            competition=competition,
        )

        preview = HistoricalImportPreview(
            preview_uuid=str(uuid.uuid4()),
            filename=f"research-{entity_type}.txt",
            provider=provider.strip(),
            competition_code=competition.strip().upper(),
            status="research",
            rows_json=json.dumps({
                "entity_type": entity_type,
                "raw_text": raw_text,
                "mapping": mapping,
                "canonical_csv": canonical_csv,
            }, separators=(",", ":")),
            report_json=json.dumps({
                "headers": table.headers,
                "row_count": len(table.rows),
                "delimiter": table.delimiter,
                "mapped_count": sum(1 for value in mapping.values() if value),
            }, separators=(",", ":")),
        )
        db.add(preview)
        db.commit()
        db.refresh(preview)
        return preview

    @staticmethod
    def session(db, preview_uuid: str) -> Optional[HistoricalImportPreview]:
        return db.query(HistoricalImportPreview).filter_by(preview_uuid=preview_uuid).first()

    @staticmethod
    def payload(preview: HistoricalImportPreview) -> dict:
        return json.loads(preview.rows_json)

    @staticmethod
    def report(preview: HistoricalImportPreview) -> dict:
        return json.loads(preview.report_json)

    @staticmethod
    def _normalise_value(field: str, value: str) -> str:
        value = value.strip()
        if field == "checkout_percentage":
            return value.rstrip("%").strip()
        if field == "decimal_odds" and "/" in value:
            numerator, denominator = value.split("/", 1)
            return str(round(1 + float(numerator) / float(denominator), 6))
        return value

    @staticmethod
    def _source_id(entity_type: str, row: Mapping[str, str], index: int) -> str:
        candidates = {
            "fixtures": row.get("external_id"),
            "results": row.get("match_external_id"),
            "statistics": f"{row.get('match_external_id', '')}:{row.get('player_external_id', '')}",
            "odds": ":".join((
                row.get("match_external_id", ""),
                row.get("bookmaker", ""),
                row.get("market", ""),
                row.get("selection_name", ""),
                row.get("captured_at", ""),
            )),
        }
        value = candidates.get(entity_type) or f"research-{entity_type}-{index}"
        return slug(value)
