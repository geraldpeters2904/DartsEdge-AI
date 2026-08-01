from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)


class FakeCaptureProvider:
    """Deterministic provider for workflow integration tests."""

    name = "fake"

    def __init__(
        self,
        *,
        html: Optional[str] = None,
        fail_message: Optional[str] = None,
    ) -> None:
        self.html = html
        self.fail_message = fail_message
        self.capture_calls = []

    def capture(
        self,
        request: CaptureRequest,
    ) -> CaptureResult:
        self.capture_calls.append(request)

        if self.fail_message:
            return CaptureResult(
                provider=self.name,
                status="failed",
                match_id=request.match_id,
                destination_path=None,
                message=(
                    f"Fake provider failed for match "
                    f"{request.match_id}."
                ),
                source_url=request.source_url,
                captured_at=datetime.utcnow().isoformat(),
                error=self.fail_message,
            )

        html = self.html or (
            "<html><body>"
            f"Match {request.match_id} "
            f"{request.player_a_name} vs "
            f"{request.player_b_name}"
            "</body></html>"
        )

        return CaptureResult(
            provider=self.name,
            status="captured",
            match_id=request.match_id,
            destination_path=None,
            message=(
                f"Fake provider captured match "
                f"{request.match_id}."
            ),
            html=html,
            source_url=request.source_url,
            page_title=(
                f"{request.player_a_name} vs "
                f"{request.player_b_name}"
            ),
            captured_at=datetime.utcnow().isoformat(),
        )
