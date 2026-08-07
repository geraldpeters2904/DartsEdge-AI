from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.services.browser_session import BrowserSession
from app.services.capture_provider import CaptureRequest, CaptureResult
from app.services.chrome_browser_session import ChromeBrowserSession


class ChromeCaptureProvider:
    """Capture one rendered match page through dedicated Chrome."""

    name = "chrome"

    def __init__(self, *, browser_session: Optional[BrowserSession] = None, timeout_seconds: float = 30.0) -> None:
        self.browser_session = browser_session or ChromeBrowserSession()
        self.timeout_seconds = timeout_seconds

    def capture(self, request: CaptureRequest) -> CaptureResult:
        try:
            self.browser_session.goto(request.source_url, timeout_seconds=self.timeout_seconds)
            self.browser_session.wait_for(
                lambda: self._expected_page_loaded(request),
                timeout_seconds=self.timeout_seconds,
                description=f"MODUS match {request.match_id} content",
            )
            html = self.browser_session.html()
            title = self.browser_session.title()
            current_url = self.browser_session.current_url()
            self._validate_page(request=request, html=html, title=title, current_url=current_url)
            return CaptureResult(
                provider=self.name,
                status="captured",
                match_id=request.match_id,
                destination_path=None,
                message=f"Chrome captured match {request.match_id}.",
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
                message=f"Chrome could not capture match {request.match_id}.",
                source_url=request.source_url,
                captured_at=datetime.utcnow().isoformat(),
                error=str(exc),
            )

    def close(self) -> None:
        self.browser_session.close()

    def _expected_page_loaded(self, request: CaptureRequest) -> bool:
        lowered = self.browser_session.html().casefold()
        names = [n.strip().casefold() for n in (request.player_a_name, request.player_b_name) if n and n.strip()]
        return str(request.match_id) in lowered or (len(names) == 2 and all(n in lowered for n in names))

    @staticmethod
    def _validate_page(*, request: CaptureRequest, html: str, title: str, current_url: str) -> None:
        lowered = html.casefold()
        if "<html" not in lowered:
            raise ValueError("Chrome did not return a complete HTML document.")
        names = [n.strip().casefold() for n in (request.player_a_name, request.player_b_name) if n and n.strip()]
        if not (str(request.match_id) in lowered or (len(names) == 2 and all(n in lowered for n in names))):
            raise ValueError(f"Chrome page does not match expected MODUS match {request.match_id}.")
        combined = f"{title} {current_url} {html[:5000]}".casefold()
        blocked = next((m for m in {"captcha", "access denied", "forbidden", "verify you are human", "cloudflare challenge"} if m in combined), None)
        if blocked is not None:
            raise ValueError(f"Chrome capture stopped because the page contains an access challenge: {blocked}.")
