from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Mapping, Optional

from app.services.bookmaker_adapter_types import (
    BookmakerAdapterResult,
    BookmakerQuote,
)


class BookmakerAdapter(ABC):
    bookmaker_code: str
    bookmaker_name: str

    @abstractmethod
    def extract_quotes(
        self,
        payload,
        *,
        captured_at: Optional[datetime] = None,
    ) -> BookmakerAdapterResult:
        raise NotImplementedError

    def _normalise_market(
        self,
        value: str,
    ) -> str:
        text = str(value or "").strip().lower()

        aliases = {
            "match winner": "match_winner",
            "match_winner": "match_winner",
            "winner": "match_winner",
            "moneyline": "match_winner",
        }

        return aliases.get(
            text,
            text.replace(" ", "_"),
        )

    def _normalise_selection(
        self,
        value: str,
    ) -> str:
        return " ".join(
            str(value or "")
            .strip()
            .split()
        )

    def _normalise_decimal_odds(
        self,
        value,
    ) -> float:
        price = float(value)

        if price <= 1.0:
            raise ValueError(
                "Decimal odds must be greater than 1.0."
            )

        return round(
            price,
            4,
        )

    def _quote(
        self,
        *,
        fixture_id: int,
        market: str,
        selection: str,
        decimal_odds,
        captured_at: datetime,
        source_reference: Optional[str] = None,
    ) -> BookmakerQuote:
        return BookmakerQuote(
            bookmaker_code=self.bookmaker_code,
            fixture_id=int(fixture_id),
            market=self._normalise_market(
                market
            ),
            selection=self._normalise_selection(
                selection
            ),
            decimal_odds=self._normalise_decimal_odds(
                decimal_odds
            ),
            captured_at=captured_at,
            source_reference=source_reference,
        )

    def _result(
        self,
        quotes: Iterable[
            BookmakerQuote
        ],
    ) -> BookmakerAdapterResult:
        rows = tuple(
            quotes
        )

        return BookmakerAdapterResult(
            bookmaker_code=self.bookmaker_code,
            quote_count=len(
                rows
            ),
            quotes=rows,
            message=(
                f"{self.bookmaker_name}: "
                f"{len(rows)} quote(s) extracted."
            ),
        )
