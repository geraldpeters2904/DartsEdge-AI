from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.providers.adapters.modus_official.urls import (
    ModusUrlModel,
)
from app.services.automatic_modus_fixture_import_service import (
    AutomaticModusFixtureImportResult,
    AutomaticModusFixtureImportService,
)
from app.services.browser_session import BrowserSession
from app.services.safari_browser_session import (
    SafariBrowserSession,
)


@dataclass(frozen=True)
class ModusFixtureDiscoveryResult:
    source_url: str
    current_url: str
    page_title: str
    checksum: str
    changed: bool
    action: str
    message: str
    import_result: Optional[
        AutomaticModusFixtureImportResult
    ] = None

    @property
    def imported(self) -> bool:
        return self.action == "imported"

    @property
    def unchanged(self) -> bool:
        return self.action == "unchanged"


class ModusFixtureDiscoveryService:
    """
    Fetch and import one official MODUS results/fixtures page.

    A rendered Safari page is used so dynamic fixture cards are available.
    Checksums prevent repeat commits during the lifetime of this service.
    Warehouse commits remain duplicate-safe if the service restarts.
    """

    def __init__(
        self,
        *,
        browser_session: Optional[
            BrowserSession
        ] = None,
        fixture_import_service: Optional[
            AutomaticModusFixtureImportService
        ] = None,
        url_model: Optional[ModusUrlModel] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.browser_session = (
            browser_session or SafariBrowserSession()
        )
        self.fixture_import_service = (
            fixture_import_service
            or AutomaticModusFixtureImportService()
        )
        self.url_model = url_model or ModusUrlModel()
        self.timeout_seconds = timeout_seconds
        self._last_checksums: Dict[str, str] = {}

    def discover(
        self,
        db: Session,
        *,
        series_id: int,
        week_id: int,
        group: str,
    ) -> ModusFixtureDiscoveryResult:
        source_url = self.url_model.results_url(
            series_id=series_id,
            week_id=week_id,
            group=group,
        )

        self.browser_session.goto(
            source_url,
            timeout_seconds=self.timeout_seconds,
        )

        self.browser_session.wait_for(
            self._fixture_cards_loaded,
            timeout_seconds=self.timeout_seconds,
            description="MODUS fixture cards",
        )

        html = self.browser_session.html()
        current_url = (
            self.browser_session.current_url()
            or source_url
        )
        title = self.browser_session.title()
        checksum = hashlib.sha256(
            html.encode("utf-8")
        ).hexdigest()

        previous = self._last_checksums.get(source_url)

        if previous == checksum:
            return ModusFixtureDiscoveryResult(
                source_url=source_url,
                current_url=current_url,
                page_title=title,
                checksum=checksum,
                changed=False,
                action="unchanged",
                message=(
                    "The MODUS fixtures page has not changed "
                    "since the last discovery cycle."
                ),
            )

        import_result = (
            self.fixture_import_service.import_html(
                db,
                html_text=html,
                source_name=(
                    f"modus-series-{series_id}-week-"
                    f"{week_id}-{group}.html"
                ),
            )
        )

        self._last_checksums[source_url] = checksum

        return ModusFixtureDiscoveryResult(
            source_url=source_url,
            current_url=current_url,
            page_title=title,
            checksum=checksum,
            changed=True,
            action="imported",
            message=(
                f"Discovered and imported "
                f"{import_result.fixture_count} MODUS fixture(s)."
            ),
            import_result=import_result,
        )

    def close(self) -> None:
        self.browser_session.close()

    def _fixture_cards_loaded(self) -> bool:
        html = self.browser_session.html().casefold()

        return (
            "match-db-stats.php?match_id=" in html
            and 'id="seriesselect"' in html
            and 'id="weekselect"' in html
        )
