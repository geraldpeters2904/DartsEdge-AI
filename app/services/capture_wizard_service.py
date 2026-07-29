from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import List

from app.services.capture_library_service import DEFAULT_CAPTURE_ROOT
from app.services.modus_capture_session_service import (
    ModusCaptureSession,
    ModusCaptureSessionService,
)


_GROUP_FOLDER = {
    "Group A": "Group_A",
    "Group B": "Group_B",
    "Group C": "Group_C",
    "Final": "Final",
}


@dataclass(frozen=True)
class CaptureWizardCreatedSession:
    source_filename: str
    destination_folder: Path
    series_label: str
    week_label: str
    group: str
    expected_count: int
    captured_count: int
    resume_url: str


@dataclass(frozen=True)
class CaptureWizardResult:
    root: Path
    created: List[CaptureWizardCreatedSession]
    errors: List[str]

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class CaptureWizardService:
    """
    Create standard capture folders and sessions from saved MODUS results HTML.

    The wizard is offline. Each uploaded results page is parsed to determine
    its own Series, Week and Group before the destination folder is created.
    """

    def __init__(self):
        self.session_service = ModusCaptureSessionService()

    def create_from_pages(
        self,
        *,
        capture_root: str | Path = DEFAULT_CAPTURE_ROOT,
        saved_pages: List[tuple[str, str]],
    ) -> CaptureWizardResult:
        root = Path(capture_root).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)

        if not root.is_dir():
            raise ValueError(f"Capture root is not a folder: {root}")

        if not saved_pages:
            raise ValueError("Select at least one saved MODUS results page.")

        created: List[CaptureWizardCreatedSession] = []
        errors: List[str] = []

        seen_destinations = set()

        for filename, html in saved_pages:
            try:
                page = self.session_service.results_parser.parse_results_document(
                    html
                )
                destination = self._destination_for_page(root, page)

                if destination in seen_destinations:
                    raise ValueError(
                        "More than one uploaded page maps to "
                        f"{page.series_label}, {page.week_label}, {page.group}."
                    )
                seen_destinations.add(destination)

                session = self.session_service.create_session(
                    results_filename=filename,
                    results_html=html,
                    destination_folder=destination,
                )
                created.append(
                    self._created_session(filename, session)
                )
            except Exception as exc:
                errors.append(f"{filename}: {exc}")

        return CaptureWizardResult(
            root=root,
            created=created,
            errors=errors,
        )

    @staticmethod
    def _destination_for_page(root: Path, page) -> Path:
        series_number = CaptureWizardService._number_from_label(
            page.series_label,
            "Series",
        )
        week_number = CaptureWizardService._number_from_label(
            page.week_label,
            "Week",
        )
        group_folder = _GROUP_FOLDER.get(page.group)

        if group_folder is None:
            raise ValueError(f"Unsupported MODUS group: {page.group}")

        return (
            root
            / f"Series_{series_number:02d}"
            / f"Week_{week_number:02d}"
            / group_folder
        )

    @staticmethod
    def _number_from_label(label: str, prefix: str) -> int:
        match = re.fullmatch(
            rf"{re.escape(prefix)}\s+(\d+)",
            (label or "").strip(),
            flags=re.IGNORECASE,
        )
        if not match:
            raise ValueError(
                f"Unable to derive {prefix.lower()} number from {label!r}."
            )
        return int(match.group(1))

    @staticmethod
    def _created_session(
        source_filename: str,
        session: ModusCaptureSession,
    ) -> CaptureWizardCreatedSession:
        from urllib.parse import quote

        return CaptureWizardCreatedSession(
            source_filename=source_filename,
            destination_folder=session.destination_folder,
            series_label=session.series_label,
            week_label=session.week_label,
            group=session.group,
            expected_count=session.expected_count,
            captured_count=session.captured_count,
            resume_url=(
                "/admin/collector/capture/modus?folder="
                + quote(str(session.destination_folder))
            ),
        )
