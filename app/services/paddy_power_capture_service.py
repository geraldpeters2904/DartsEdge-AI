from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable, Optional, Protocol

from sqlalchemy.orm import Session

from app.services.bookmaker_capture_service import (
    store_price_changes,
)
from app.services.bookmaker_capture_types import (
    BookmakerCaptureReport,
    CapturedBookmakerPrice,
)
from app.services.chrome_browser_session import (
    ChromeBrowserSession,
)


class PaddyPowerExtractor(Protocol):
    def extract(
        self,
        html: str,
        *,
        captured_at: datetime,
    ) -> Iterable[
        CapturedBookmakerPrice
    ]:
        ...


class PaddyPowerCaptureService:
    BOOKMAKER = "Paddy Power"

    CHALLENGE_MARKERS = (
        "access denied",
        "are you a human",
        "verify you are human",
        "captcha",
        "unusual traffic",
    )

    def __init__(
        self,
        *,
        browser_session: Optional[
            ChromeBrowserSession
        ] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.browser_session = (
            browser_session
            or ChromeBrowserSession()
        )
        self.timeout_seconds = float(
            timeout_seconds
        )

    def capture(
        self,
        db: Session,
        *,
        source_url: str,
        extractor: PaddyPowerExtractor,
        page_ready: Optional[
            Callable[[str], bool]
        ] = None,
    ) -> BookmakerCaptureReport:
        captured_at = datetime.utcnow()

        self.browser_session.goto(
            source_url,
            timeout_seconds=(
                self.timeout_seconds
            ),
        )

        self.browser_session.wait_for(
            lambda: (
                page_ready(
                    self.browser_session
                    .html()
                )
                if page_ready
                else bool(
                    self.browser_session
                    .html()
                    .strip()
                )
            ),
            timeout_seconds=(
                self.timeout_seconds
            ),
            description=(
                "Paddy Power page content"
            ),
        )

        html = (
            self.browser_session
            .html()
        )

        lowered = html.casefold()

        challenge_detected = any(
            marker in lowered
            for marker
            in self.CHALLENGE_MARKERS
        )

        if challenge_detected:
            return BookmakerCaptureReport(
                bookmaker=self.BOOKMAKER,
                source_url=source_url,
                captured_at=captured_at,
                extracted_prices=0,
                stored_prices=0,
                unchanged_prices=0,
                skipped_prices=0,
                challenge_detected=True,
                message=(
                    "Paddy Power presented an access or verification "
                    "challenge. Capture stopped without attempting bypass."
                ),
            )

        extracted = list(
            extractor.extract(
                html,
                captured_at=captured_at,
            )
        )

        cleaned = []

        for price in extracted:
            if (
                price.bookmaker
                and price.bookmaker
                != self.BOOKMAKER
            ):
                price = (
                    CapturedBookmakerPrice(
                        fixture_date=(
                            price.fixture_date
                        ),
                        tournament=(
                            price.tournament
                        ),
                        player_a=(
                            price.player_a
                        ),
                        player_b=(
                            price.player_b
                        ),
                        market=(
                            price.market
                        ),
                        selection=(
                            price.selection
                        ),
                        bookmaker=(
                            self.BOOKMAKER
                        ),
                        decimal_odds=(
                            price.decimal_odds
                        ),
                        captured_at=(
                            price.captured_at
                        ),
                        provider_id=(
                            price.provider_id
                        ),
                    )
                )

            cleaned.append(
                price
            )

        persistence = (
            store_price_changes(
                db,
                cleaned,
            )
        )

        return BookmakerCaptureReport(
            bookmaker=self.BOOKMAKER,
            source_url=source_url,
            captured_at=captured_at,
            extracted_prices=len(
                cleaned
            ),
            stored_prices=(
                persistence[
                    "stored"
                ]
            ),
            unchanged_prices=(
                persistence[
                    "unchanged"
                ]
            ),
            skipped_prices=(
                persistence[
                    "skipped"
                ]
            ),
            challenge_detected=False,
            message=(
                "Paddy Power capture completed."
            ),
        )

    def close(self) -> None:
        self.browser_session.close()
