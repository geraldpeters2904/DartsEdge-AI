from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Dict, List

from app.collector.csv_definitions import allowed_headers
from app.schemas.canonical import CanonicalFixture
from app.services.modus_fixture_lifecycle_service import (
    ModusFixtureLifecycleService,
)


@dataclass(frozen=True)
class ModusFixtureImportPayload:
    fixtures: List[CanonicalFixture]
    csv_by_type: Dict[str, str]
    filenames: Dict[str, str]

    @property
    def fixture_count(self) -> int:
        return len(self.fixtures)

    @property
    def scheduled_count(self) -> int:
        return sum(
            1 for fixture in self.fixtures
            if fixture.status.value == "scheduled"
        )

    @property
    def completed_count(self) -> int:
        return sum(
            1 for fixture in self.fixtures
            if fixture.status.value == "completed"
        )

    def to_dict(self) -> dict:
        return {
            "fixture_count": self.fixture_count,
            "scheduled_count": self.scheduled_count,
            "completed_count": self.completed_count,
            "filenames": dict(self.filenames),
        }


class ModusFixtureImportService:
    """Build a fixture-only Collector Preview payload from saved MODUS HTML."""

    def __init__(self):
        self.lifecycle_service = ModusFixtureLifecycleService()

    def build_payload(self, html_text: str) -> ModusFixtureImportPayload:
        preview = self.lifecycle_service.build_canonical_fixtures(html_text)
        fixtures = preview.fixtures

        if not fixtures:
            raise ValueError("No canonical MODUS fixtures were produced.")

        csv_by_type = {
            "fixtures": self._fixtures_to_csv(fixtures),
        }
        filenames = {
            "fixtures": "modus_fixtures.csv",
        }

        return ModusFixtureImportPayload(
            fixtures=fixtures,
            csv_by_type=csv_by_type,
            filenames=filenames,
        )

    @staticmethod
    def _fixtures_to_csv(fixtures: List[CanonicalFixture]) -> str:
        headers = list(allowed_headers("fixtures"))
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for fixture in fixtures:
            data = fixture.model_dump(mode="json")
            source = data.pop("source")
            row = {header: "" for header in headers}

            for key, value in data.items():
                if key in row and value is not None:
                    row[key] = value

            row.update(
                {
                    "source_provider": source["provider"],
                    "source_external_id": source["external_id"],
                    "source_retrieved_at": source["retrieved_at"],
                    "source_competition_code": (
                        source.get("competition_code") or ""
                    ),
                    "source_confidence": source["confidence"],
                }
            )
            writer.writerow(row)

        return output.getvalue()
