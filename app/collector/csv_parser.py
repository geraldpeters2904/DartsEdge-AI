from __future__ import annotations

import csv
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class CsvParseIssue:
    """One problem or warning found while parsing a CSV file."""

    severity: str
    code: str
    message: str
    row_number: Optional[int] = None
    field_name: Optional[str] = None


@dataclass
class CsvParseResult:
    """Result returned after parsing and validating one CSV document."""

    filename: str
    headers: List[str] = field(default_factory=list)
    records: List[Dict[str, Optional[str]]] = field(default_factory=list)
    issues: List[CsvParseIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(
            1 for issue in self.issues
            if issue.severity == "error"
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1 for issue in self.issues
            if issue.severity == "warning"
        )

    @property
    def valid(self) -> bool:
        return self.error_count == 0


class CanonicalCsvParser:
    """
    Parse CSV text into normalised dictionaries.

    This parser performs structural validation only. Canonical Pydantic
    validation and import-session validation are handled in later stages.
    """

    def parse_text(
        self,
        csv_text: str,
        *,
        filename: str = "<memory>",
        required_headers: Sequence[str] = (),
        allowed_headers: Optional[Sequence[str]] = None,
    ) -> CsvParseResult:
        result = CsvParseResult(filename=filename)

        if not isinstance(csv_text, str):
            result.issues.append(
                CsvParseIssue(
                    severity="error",
                    code="invalid_input",
                    message="CSV input must be text.",
                )
            )
            return result

        stream = StringIO(csv_text.lstrip("\ufeff"))
        reader = csv.DictReader(stream)

        if reader.fieldnames is None:
            result.issues.append(
                CsvParseIssue(
                    severity="error",
                    code="missing_header",
                    message="CSV file does not contain a header row.",
                )
            )
            return result

        headers = [
            self.normalise_header(header)
            for header in reader.fieldnames
            if header is not None
        ]
        result.headers = headers

        for duplicate in self.find_duplicates(headers):
            result.issues.append(
                CsvParseIssue(
                    severity="error",
                    code="duplicate_header",
                    message=f"Duplicate CSV header: {duplicate}",
                    field_name=duplicate,
                )
            )

        required = [
            self.normalise_header(header)
            for header in required_headers
        ]

        for header in required:
            if header not in headers:
                result.issues.append(
                    CsvParseIssue(
                        severity="error",
                        code="missing_required_header",
                        message=f"Missing required CSV header: {header}",
                        field_name=header,
                    )
                )

        if allowed_headers is not None:
            allowed = {
                self.normalise_header(header)
                for header in allowed_headers
            }

            for header in headers:
                if header not in allowed:
                    result.issues.append(
                        CsvParseIssue(
                            severity="error",
                            code="unknown_header",
                            message=f"Unknown CSV header: {header}",
                            field_name=header,
                        )
                    )

        if result.error_count:
            return result

        for row_number, raw_row in enumerate(reader, start=2):
            record = {
                self.normalise_header(key): self.clean_value(value)
                for key, value in raw_row.items()
                if key is not None
            }

            if self.row_is_blank(record):
                continue

            missing_values = [
                header
                for header in required
                if record.get(header) is None
            ]

            if missing_values:
                for field_name in missing_values:
                    result.issues.append(
                        CsvParseIssue(
                            severity="error",
                            code="missing_required_value",
                            message=(
                                "Required CSV value is missing: "
                                f"{field_name}"
                            ),
                            row_number=row_number,
                            field_name=field_name,
                        )
                    )
                continue

            result.records.append(record)

        if not result.records and result.error_count == 0:
            result.issues.append(
                CsvParseIssue(
                    severity="warning",
                    code="empty_file",
                    message="CSV file contains no data rows.",
                )
            )

        return result

    def parse_file(
        self,
        path: Path,
        *,
        required_headers: Sequence[str] = (),
        allowed_headers: Optional[Sequence[str]] = None,
    ) -> CsvParseResult:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(path)

        csv_text = path.read_text(encoding="utf-8-sig")

        return self.parse_text(
            csv_text,
            filename=path.name,
            required_headers=required_headers,
            allowed_headers=allowed_headers,
        )

    @staticmethod
    def normalise_header(value: str) -> str:
        return (
            value
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    @staticmethod
    def clean_value(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            return None

        if cleaned.casefold() in {
            "null",
            "none",
            "n/a",
            "na",
        }:
            return None

        return cleaned

    @staticmethod
    def row_is_blank(
        record: Mapping[str, Optional[str]],
    ) -> bool:
        return all(value is None for value in record.values())

    @staticmethod
    def find_duplicates(
        values: Sequence[str],
    ) -> List[str]:
        seen = set()
        duplicates = []

        for value in values:
            if value in seen and value not in duplicates:
                duplicates.append(value)

            seen.add(value)

        return duplicates
