from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.services.browser_session import BrowserSession
from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.safari_browser_session import (
    SafariBrowserSession,
)


class SafariCaptureProvider:
    """Capture one rendered match page through Safari WebDriver."""

    name = "safari"

    def __init__(
        self,
        *,
        browser_session: Optional[BrowserSession] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.browser_session = (
            browser_session or SafariBrowserSession()
        )
        self.timeout_seconds = timeout_seconds

    def capture(
        self,
        request: CaptureRequest,
    ) -> CaptureResult:
        try:
            self.browser_session.goto(
                request.source_url,
                timeout_seconds=self.timeout_seconds,
            )

            self.browser_session.wait_for(
                lambda: self._expected_page_loaded(request),
                timeout_seconds=self.timeout_seconds,
                description=(
                    f"MODUS match {request.match_id} content"
                ),
            )

            html = self.browser_session.html()
            title = self.browser_session.title()
            current_url = self.browser_session.current_url()

            self._validate_page(
                request=request,
                html=html,
                title=title,
                current_url=current_url,
            )

            return CaptureResult(
                provider=self.name,
                status="captured",
                match_id=request.match_id,
                destination_path=None,
                message=(
                    f"Safari captured match {request.match_id}."
                ),
                html=html,
                source_url=current_url or request.source_url,
                page_title=title,
                captured_at=datetime.utcnow().isoformat(),
            )

        except Exception as exc:
            return CaptureResult(
                provider=self.name,
                status="failed",
                match_id=request.match_id,
                destination_path=None,
                message=(
                    f"Safari could not capture match "
                    f"{request.match_id}."
                ),
                source_url=request.source_url,
                captured_at=datetime.utcnow().isoformat(),
                error=str(exc),
            )

    def close(self) -> None:
        self.browser_session.close()

    def _expected_page_loaded(
        self,
        request: CaptureRequest,
    ) -> bool:
        html = self.browser_session.html()
        lowered = html.casefold()

        match_id_present = str(request.match_id) in lowered

        names = [
            name.strip().casefold()
            for name in (
                request.player_a_name,
                request.player_b_name,
            )
            if name and name.strip()
        ]

        both_names_present = (
            len(names) == 2
            and all(name in lowered for name in names)
        )

        return match_id_present or both_names_present

    @staticmethod
    def _validate_page(
        *,
        request: CaptureRequest,
        html: str,
        title: str,
        current_url: str,
    ) -> None:
        lowered = html.casefold()

        if "<html" not in lowered:
            raise ValueError(
                "Safari did not return a complete HTML document."
            )

        match_id_present = str(request.match_id) in lowered

        expected_names = [
            name.strip().casefold()
            for name in (
                request.player_a_name,
                request.player_b_name,
            )
            if name and name.strip()
        ]

        both_names_present = (
            len(expected_names) == 2
            and all(
                name in lowered
                for name in expected_names
            )
        )

        if not (match_id_present or both_names_present):
            raise ValueError(
                "Safari page does not match expected MODUS "
                f"match {request.match_id}."
            )

        combined = (
            f"{title} {current_url} {html[:5000]}"
        ).casefold()

        blocked_markers = {
            "captcha",
            "access denied",
            "forbidden",
            "verify you are human",
            "cloudflare challenge",
        }

        marker = next(
            (
                value
                for value in blocked_markers
                if value in combined
            ),
            None,
        )

        if marker is not None:
            raise ValueError(
                "Safari capture stopped because the page "
                f"contains an access challenge: {marker}."
            )
