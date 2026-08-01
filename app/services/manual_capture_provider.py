from __future__ import annotations

from datetime import datetime

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)


class ManualCaptureProvider:
    """
    Manual capture provider.

    It does not fetch webpages. It reports that the workflow is waiting for
    the user and the existing Capture Assistant, or confirms that the expected
    destination file already exists.
    """

    name = "manual"

    def capture(
        self,
        request: CaptureRequest,
    ) -> CaptureResult:
        if request.destination_path.is_file():
            return CaptureResult(
                provider=self.name,
                status="captured",
                match_id=request.match_id,
                destination_path=request.destination_path,
                message=(
                    f"Match {request.match_id} is already captured."
                ),
                source_url=request.source_url,
                captured_at=datetime.utcnow().isoformat(),
            )

        return CaptureResult(
            provider=self.name,
            status="waiting",
            match_id=request.match_id,
            destination_path=None,
            message=(
                f"Waiting for match {request.match_id} "
                "to be saved through the Capture Assistant."
            ),
            source_url=request.source_url,
        )
