from __future__ import annotations

from dataclasses import dataclass

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)


ACCESS_CHALLENGE_MARKERS = (
    "captcha",
    "access denied",
    "forbidden",
    "verify you are human",
    "cloudflare challenge",
    "checking your browser",
)

LOGIN_MARKERS = (
    "login required",
    "sign in to continue",
    "session expired",
)


@dataclass(frozen=True)
class CaptureValidationResult:
    valid: bool
    retryable: bool
    message: str
    marker: str | None = None


class CaptureValidationService:
    """Validate captured HTML before it is persisted."""

    def validate(
        self,
        request: CaptureRequest,
        result: CaptureResult,
    ) -> CaptureValidationResult:
        if not result.has_html:
            return CaptureValidationResult(
                valid=False,
                retryable=True,
                message="Capture provider returned no HTML.",
            )

        html = result.html or ""
        lowered = html.casefold()

        if "<html" not in lowered:
            return CaptureValidationResult(
                valid=False,
                retryable=True,
                message=(
                    "Capture provider did not return a complete "
                    "HTML document."
                ),
            )

        combined = (
            f"{result.page_title or ''} "
            f"{result.source_url or ''} "
            f"{html[:5000]}"
        ).casefold()

        marker = next(
            (
                value
                for value in ACCESS_CHALLENGE_MARKERS
                if value in combined
            ),
            None,
        )

        if marker is not None:
            return CaptureValidationResult(
                valid=False,
                retryable=True,
                message=(
                    "Capture page contains an access challenge: "
                    f"{marker}."
                ),
                marker=marker,
            )

        marker = next(
            (
                value
                for value in LOGIN_MARKERS
                if value in combined
            ),
            None,
        )

        if marker is not None:
            return CaptureValidationResult(
                valid=False,
                retryable=False,
                message=(
                    "Capture page requires authentication: "
                    f"{marker}."
                ),
                marker=marker,
            )

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

        if not (match_id_present or both_names_present):
            return CaptureValidationResult(
                valid=False,
                retryable=False,
                message=(
                    "Capture page does not match expected match "
                    f"{request.match_id}."
                ),
            )

        return CaptureValidationResult(
            valid=True,
            retryable=False,
            message="Capture page passed validation.",
        )
