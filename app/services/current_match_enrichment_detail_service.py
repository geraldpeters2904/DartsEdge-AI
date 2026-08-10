from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
)
from app.providers.adapters.modus_official.urls import ModusUrlModel
from app.services.chrome_browser_session import ChromeBrowserSession
from app.services.current_match_enrichment_discovery_service import (
    EnrichmentCandidate,
)


@dataclass(frozen=True)
class CurrentMatchEnrichmentDetailResult:
    internal_match_id: int
    modus_match_id: int
    source_url: str
    player_a: str
    player_b: str
    player_a_legs: int
    player_b_legs: int
    detail: object
    status: str
    message: str


def _normalise_name(value: Optional[str]) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _player_pair(
    player_a: Optional[str],
    player_b: Optional[str],
) -> frozenset[str]:
    return frozenset(
        (
            _normalise_name(player_a),
            _normalise_name(player_b),
        )
    )


class CurrentMatchEnrichmentDetailService:
    """
    Fetch and validate one resolved official MODUS match page.

    This service is intentionally read-only. It does not create mappings,
    performance rows, provenance, or import batches.
    """

    def __init__(
        self,
        *,
        browser_factory=ChromeBrowserSession,
        parser: Optional[ModusRealMatchPageParser] = None,
        url_model: Optional[ModusUrlModel] = None,
    ) -> None:
        self.browser_factory = browser_factory
        self.parser = parser or ModusRealMatchPageParser()
        self.url_model = url_model or ModusUrlModel()

    def fetch(
        self,
        candidate: EnrichmentCandidate,
        *,
        timeout_seconds: float = 30.0,
    ) -> CurrentMatchEnrichmentDetailResult:
        if candidate.status != "resolved":
            raise ValueError(
                "Only resolved enrichment candidates can be fetched."
            )

        if candidate.resolved_modus_match_id is None:
            raise ValueError(
                "Resolved enrichment candidate has no MODUS match ID."
            )

        modus_match_id = int(
            candidate.resolved_modus_match_id
        )

        source_url = self.url_model.match_stats_url(
            modus_match_id
        )

        browser = self.browser_factory()

        try:
            browser.goto(
                source_url,
                timeout_seconds=timeout_seconds,
            )

            html = browser.html()

            detail = self.parser.parse(
                html,
                match_id=modus_match_id,
            )
        finally:
            close = getattr(
                browser,
                "close",
                None,
            )

            if callable(close):
                close()

        expected_pair = _player_pair(
            candidate.player_a,
            candidate.player_b,
        )

        actual_pair = _player_pair(
            detail.player_a_name,
            detail.player_b_name,
        )

        if expected_pair != actual_pair:
            raise ValueError(
                "Official MODUS match players do not match "
                "the internal enrichment candidate: "
                f"{candidate.player_a} v {candidate.player_b} "
                "!= "
                f"{detail.player_a_name} v "
                f"{detail.player_b_name}."
            )

        return CurrentMatchEnrichmentDetailResult(
            internal_match_id=int(
                candidate.internal_match_id
            ),
            modus_match_id=modus_match_id,
            source_url=source_url,
            player_a=detail.player_a_name,
            player_b=detail.player_b_name,
            player_a_legs=int(
                detail.player_a_legs
            ),
            player_b_legs=int(
                detail.player_b_legs
            ),
            detail=detail,
            status="validated",
            message=(
                "Official MODUS match detail fetched and "
                "validated against the internal fixture."
            ),
        )
