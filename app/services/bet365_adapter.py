from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.services.bookmaker_adapter_base import (
    BookmakerAdapter,
)


class Bet365Adapter(
    BookmakerAdapter
):
    bookmaker_code = "bet365"
    bookmaker_name = "Bet365"

    def extract_quotes(
        self,
        payload,
        *,
        captured_at: Optional[
            datetime
        ] = None,
    ):
        captured = (
            captured_at
            or datetime.utcnow()
        )

        quotes = []

        for row in payload or []:
            quotes.append(
                self._quote(
                    fixture_id=(
                        row["fixture_id"]
                    ),
                    market=(
                        row.get(
                            "market",
                            "match_winner",
                        )
                    ),
                    selection=(
                        row["selection"]
                    ),
                    decimal_odds=(
                        row["decimal_odds"]
                    ),
                    captured_at=(
                        captured
                    ),
                    source_reference=(
                        row.get(
                            "source_reference"
                        )
                    ),
                )
            )

        return self._result(
            quotes
        )
