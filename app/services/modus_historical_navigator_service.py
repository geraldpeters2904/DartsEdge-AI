from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional

from app.services.browser_session import BrowserSession
from app.services.modus_capture_session_service import (
    ModusCaptureSession,
    ModusCaptureSessionService,
)
from app.services.modus_historical_catalog_service import (
    ModusHistoricalCaptureTarget,
    ModusHistoricalCatalogService,
)
from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)


@dataclass(frozen=True)
class ModusHistoricalNavigationResult:
    target: ModusHistoricalCaptureTarget
    destination_folder: Path
    source_url: str
    current_url: str
    page_title: str
    created: bool
    session: ModusCaptureSession

    @property
    def expected_matches(self) -> int:
        return self.session.expected_count

    @property
    def captured_matches(self) -> int:
        return self.session.captured_count

    @property
    def missing_matches(self) -> int:
        return self.session.missing_count


class ModusHistoricalNavigatorService:
    """
    Navigate to one MODUS historical results target and prepare capture.

    Dedicated Chrome loads the rendered results page. The page scope is verified
    against the requested series, week and group before results.html and
    the normal resumable capture session are written.
    """

    def __init__(
        self,
        *,
        browser_session: Optional[
            BrowserSession
        ] = None,
        catalog_service: Optional[
            ModusHistoricalCatalogService
        ] = None,
        capture_session_service: Optional[
            ModusCaptureSessionService
        ] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.browser_session = (
            browser_session or ChromeBrowserSession()
        )
        self.catalog_service = (
            catalog_service
            or ModusHistoricalCatalogService()
        )
        self.capture_session_service = (
            capture_session_service
            or ModusCaptureSessionService()
        )
        self.timeout_seconds = float(timeout_seconds)

    def prepare_target(
        self,
        *,
        root: str | Path,
        target: ModusHistoricalCaptureTarget,
    ) -> ModusHistoricalNavigationResult:
        destination = self.destination_folder(
            root=root,
            target=target,
        )
        session_file = (
            destination / ".modus_capture_session.json"
        )

        self.browser_session.goto(
            target.source_url,
            timeout_seconds=self.timeout_seconds,
        )

        self.browser_session.wait_for(
            lambda: self._target_loaded(target),
            timeout_seconds=self.timeout_seconds,
            description=(
                f"MODUS {target.series_label} "
                f"{target.week_label} {target.group}"
            ),
        )

        html = self.browser_session.html()
        selected = self.catalog_service.selected_target(
            html
        )
        self._validate_selected_target(
            expected=target,
            actual=selected,
        )

        existed = session_file.is_file()

        session = (
            self.capture_session_service.create_session(
                results_filename=self._source_filename(
                    target
                ),
                results_html=html,
                destination_folder=destination,
            )
        )

        return ModusHistoricalNavigationResult(
            target=target,
            destination_folder=destination,
            source_url=target.source_url,
            current_url=(
                self.browser_session.current_url()
                or target.source_url
            ),
            page_title=self.browser_session.title(),
            created=not existed,
            session=session,
        )

    def close(self) -> None:
        self.browser_session.close()

    def _target_loaded(
        self,
        target: ModusHistoricalCaptureTarget,
    ) -> bool:
        try:
            html = self.browser_session.html()
            selected = (
                self.catalog_service.selected_target(
                    html
                )
            )
        except Exception:
            return False

        return (
            selected.series_id == target.series_id
            and selected.week_id == target.week_id
            and selected.group == target.group
        )

    @staticmethod
    def destination_folder(
        *,
        root: str | Path,
        target: ModusHistoricalCaptureTarget,
    ) -> Path:
        root_path = Path(root).expanduser().resolve()

        return (
            root_path
            / f"Series_{target.series_id}"
            / ModusHistoricalNavigatorService._week_folder(
                target
            )
            / ModusHistoricalNavigatorService._group_folder(
                target.group
            )
        )

    @staticmethod
    def _week_folder(
        target: ModusHistoricalCaptureTarget,
    ) -> str:
        match = re.search(
            r"(\d+)",
            target.week_label or "",
        )

        if match:
            return f"Week_{int(match.group(1)):02d}"

        return f"Week_{target.week_id}"

    @staticmethod
    def _group_folder(group: str) -> str:
        clean = str(group or "").strip()

        if clean == "Final":
            return "Final"

        return clean.replace(" ", "_")

    @staticmethod
    def _source_filename(
        target: ModusHistoricalCaptureTarget,
    ) -> str:
        return (
            f"series_{target.series_id}_"
            f"week_{target.week_id}_"
            f"{target.group.replace(' ', '_').casefold()}"
            ".html"
        )

    @staticmethod
    def _validate_selected_target(
        *,
        expected: ModusHistoricalCaptureTarget,
        actual: ModusHistoricalCaptureTarget,
    ) -> None:
        mismatches = []

        if actual.series_id != expected.series_id:
            mismatches.append(
                f"series {actual.series_id}"
            )

        if actual.week_id != expected.week_id:
            mismatches.append(
                f"week {actual.week_id}"
            )

        if actual.group != expected.group:
            mismatches.append(
                f"group {actual.group}"
            )

        if mismatches:
            raise ValueError(
                "Dedicated Chrome loaded the wrong MODUS target: "
                + ", ".join(mismatches)
                + "."
            )
