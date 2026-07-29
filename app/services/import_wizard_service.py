from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.services.modus_canonical_builder import ModusCanonicalBuilder
from app.services.modus_folder_service import ModusFolderImportService


@dataclass(frozen=True)
class ImportConnectorDescriptor:
    connector_id: str
    name: str
    description: str
    enabled: bool
    input_type: str
    provider: str
    competition: str
    status_label: str


class ImportWizardService:
    """Provider-agnostic entry point for Collector import connectors."""

    def __init__(self):
        self._connectors: Dict[str, ImportConnectorDescriptor] = {
            "modus-official": ImportConnectorDescriptor(
                connector_id="modus-official",
                name="MODUS Official",
                description=(
                    "Validate saved MODUS results and match-statistics pages, "
                    "then build canonical fixtures, results and statistics."
                ),
                enabled=True,
                input_type="folder",
                provider="modus-official",
                competition="MODUS",
                status_label="Available",
            ),
            "canonical-csv": ImportConnectorDescriptor(
                connector_id="canonical-csv",
                name="Canonical CSV",
                description=(
                    "Use the existing Collector upload workflow for fixtures, "
                    "results, statistics and odds CSV files."
                ),
                enabled=True,
                input_type="redirect",
                provider="manual-research",
                competition="MODUS",
                status_label="Available",
            ),
            "excel-workbook": ImportConnectorDescriptor(
                connector_id="excel-workbook",
                name="Excel Workbook",
                description="Import mapped workbook sheets through the canonical pipeline.",
                enabled=False,
                input_type="file",
                provider="excel-import",
                competition="OTHER",
                status_label="Coming soon",
            ),
            "json-feed": ImportConnectorDescriptor(
                connector_id="json-feed",
                name="JSON Feed",
                description="Import structured provider JSON through a connector adapter.",
                enabled=False,
                input_type="file",
                provider="json-import",
                competition="OTHER",
                status_label="Coming soon",
            ),
            "pdc-official": ImportConnectorDescriptor(
                connector_id="pdc-official",
                name="PDC Official",
                description="Future official or browser-assisted PDC data connector.",
                enabled=False,
                input_type="folder",
                provider="pdc-official",
                competition="PDC",
                status_label="Coming soon",
            ),
        }

        self.modus_folder_service = ModusFolderImportService()
        self.modus_builder = ModusCanonicalBuilder()

    def connectors(self) -> List[ImportConnectorDescriptor]:
        return list(self._connectors.values())

    def connector(self, connector_id: str) -> ImportConnectorDescriptor:
        connector = self._connectors.get((connector_id or "").strip())
        if connector is None:
            raise ValueError(f"Unknown import connector: {connector_id}")
        return connector

    def validate_source(
        self,
        connector_id: str,
        source_path: str,
        *,
        allow_partial: bool = False,
    ):
        connector = self.connector(connector_id)
        if not connector.enabled:
            raise ValueError(f"{connector.name} is not enabled yet.")

        if connector.connector_id == "modus-official":
            path = self._normalise_folder(source_path)
            return self.modus_folder_service.inspect(
                path,
                allow_partial=allow_partial,
            )

        raise ValueError(
            f"{connector.name} does not support source validation in this wizard."
        )

    def build_preview_payload(
        self,
        connector_id: str,
        source_path: str,
        *,
        allow_partial: bool = False,
    ):
        connector = self.connector(connector_id)
        if not connector.enabled:
            raise ValueError(f"{connector.name} is not enabled yet.")

        if connector.connector_id == "modus-official":
            path = self._normalise_folder(source_path)
            build = self.modus_builder.build(
                path,
                allow_partial=allow_partial,
            )
            return {
                "provider": connector.provider,
                "competition": connector.competition,
                "csv_by_type": build.csv_by_type,
                "filenames": build.filenames,
                "summary": build.to_dict(),
            }

        raise ValueError(
            f"{connector.name} does not produce a Collector preview payload."
        )

    @staticmethod
    def _normalise_folder(source_path: str) -> Path:
        value = (source_path or "").strip()
        if not value:
            raise ValueError("Enter the folder containing the saved MODUS pages.")
        return Path(value).expanduser().resolve()
