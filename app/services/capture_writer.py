from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)


class CaptureWriter:
    """
    Validate and persist HTML supplied by a capture provider.

    Providers fetch content. The writer owns destination validation,
    directory creation and atomic file replacement.
    """

    def write(
        self,
        request: CaptureRequest,
        result: CaptureResult,
    ) -> CaptureResult:
        self._validate_request(request)
        self._validate_result(request, result)

        destination = request.destination_path
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = destination.with_name(
            destination.name + ".part"
        )

        html = result.html or ""
        encoded_html = html.encode("utf-8")

        try:
            temporary.write_bytes(encoded_html)
            temporary.replace(destination)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise

        return replace(
            result,
            status="captured",
            destination_path=destination,
            message=(
                f"Match {request.match_id} captured by "
                f"{result.provider} and saved as "
                f"{request.destination_filename}."
            ),
            error=None,
            bytes_written=len(encoded_html),
        )

    @staticmethod
    def _validate_request(
        request: CaptureRequest,
    ) -> None:
        if request.match_id <= 0:
            raise ValueError(
                "Capture match ID must be positive."
            )

        filename = str(
            request.destination_filename or ""
        ).strip()

        if not filename:
            raise ValueError(
                "Capture destination filename is required."
            )

        expected = f"match_{request.match_id}.html"

        if filename != expected:
            raise ValueError(
                "Capture destination filename does not match "
                f"the requested match. Expected {expected!r}."
            )

        destination = Path(
            request.destination_folder
        ).expanduser()

        if destination.exists() and not destination.is_dir():
            raise ValueError(
                "Capture destination folder is not a directory."
            )

    @staticmethod
    def _validate_result(
        request: CaptureRequest,
        result: CaptureResult,
    ) -> None:
        if result.match_id != request.match_id:
            raise ValueError(
                "Capture result match ID does not match "
                "the capture request."
            )

        if result.failed:
            raise ValueError(
                result.error
                or result.message
                or "Capture provider failed."
            )

        if result.waiting:
            raise ValueError(
                "A waiting capture result cannot be written."
            )

        if not result.has_html:
            raise ValueError(
                "Capture provider returned no HTML."
            )

        html = result.html or ""

        if "<html" not in html.casefold():
            raise ValueError(
                "Capture provider result does not appear "
                "to contain an HTML document."
            )
