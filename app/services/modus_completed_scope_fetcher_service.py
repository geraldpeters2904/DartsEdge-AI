from __future__ import annotations

from typing import Optional, Tuple

from app.providers.adapters.modus_official.urls import (
    ModusUrlModel,
)
from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)
from app.services.modus_fixture_lifecycle_service import (
    ModusFixtureLifecycleService,
)
from app.services.modus_import_scope_service import (
    ModusImportScope,
)


class ModusCompletedScopeFetcherService:

    def __init__(
        self,
        *,
        browser=None,
        lifecycle_service=None,
    ):
        self.browser = (
            browser
            if browser is not None
            else ChromeBrowserSession(headless=True)
        )
        self.lifecycle_service = (
            lifecycle_service
            if lifecycle_service is not None
            else ModusFixtureLifecycleService()
        )

    @staticmethod
    def _is_completed(card) -> bool:
        status = getattr(card, "status", None)
        value = getattr(status, "value", status)

        return str(value).casefold() == "completed"

    def fetch(
        self,
        scope: ModusImportScope,
    ) -> Tuple[object, ...]:
        url = ModusUrlModel().results_url(
            series_id=int(scope.series_id),
            week_id=int(scope.week_id),
            group=str(scope.group),
        )

        self.browser.goto(url)

        html = self.browser.html()

        cards = self.lifecycle_service.parse_cards(
            html
        )

        return tuple(
            card
            for card in cards
            if self._is_completed(card)
        )

    def close(self) -> None:
        self.browser.close()
