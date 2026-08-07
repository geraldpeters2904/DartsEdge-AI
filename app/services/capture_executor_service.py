from __future__ import annotations

from typing import Optional

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.capture_provider_registry import (
    CaptureProviderRegistry,
    capture_provider_registry,
)
from app.services.capture_validation_service import (
    CaptureValidationService,
)
from app.services.capture_writer import CaptureWriter


class CaptureExecutorService:
    """
    Execute one capture request through a selected provider.

    Providers obtain or locate content. CaptureWriter persists new HTML.
    Waiting, failed and already-written results are returned unchanged.
    """

    def __init__(
        self,
        *,
        provider_registry: Optional[
            CaptureProviderRegistry
        ] = None,
        writer: Optional[CaptureWriter] = None,
        validator: Optional[
            CaptureValidationService
        ] = None,
    ) -> None:
        self.provider_registry = (
            provider_registry or capture_provider_registry
        )
        self.writer = writer or CaptureWriter()
        self.validator = (
            validator or CaptureValidationService()
        )

    def execute(
        self,
        request: CaptureRequest,
        *,
        provider_name: str,
    ) -> CaptureResult:
        provider = self.provider_registry.get(
            provider_name
        )
        result = provider.capture(request)

        if result.waiting or result.failed:
            return result

        if result.has_html:
            validation = self.validator.validate(
                request,
                result,
            )

            if not validation.valid:
                return CaptureResult(
                    provider=result.provider,
                    status="failed",
                    match_id=result.match_id,
                    destination_path=None,
                    message="Capture validation failed.",
                    source_url=result.source_url,
                    page_title=result.page_title,
                    captured_at=result.captured_at,
                    error=validation.message,
                )

            return self.writer.write(
                request,
                result,
            )

        if result.successful and result.destination_path:
            return result

        raise ValueError(
            "Capture provider returned an unsupported result."
        )
