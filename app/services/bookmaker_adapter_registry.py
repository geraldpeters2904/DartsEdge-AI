from __future__ import annotations

from typing import Dict

from app.services.bet365_adapter import (
    Bet365Adapter,
)
from app.services.bookmaker_adapter_base import (
    BookmakerAdapter,
)
from app.services.paddy_power_adapter import (
    PaddyPowerAdapter,
)


class BookmakerAdapterRegistry:
    def __init__(
        self,
    ) -> None:
        self._adapters: Dict[
            str,
            BookmakerAdapter,
        ] = {}

    def register(
        self,
        adapter: BookmakerAdapter,
    ) -> None:
        self._adapters[
            adapter.bookmaker_code
        ] = adapter

    def get(
        self,
        bookmaker_code: str,
    ) -> BookmakerAdapter:
        code = (
            bookmaker_code
            .strip()
            .lower()
        )

        if code not in self._adapters:
            raise KeyError(
                f"No bookmaker adapter registered for {code}."
            )

        return self._adapters[
            code
        ]

    def available(
        self,
    ) -> tuple[
        str,
        ...,
    ]:
        return tuple(
            sorted(
                self._adapters.keys()
            )
        )


def default_bookmaker_registry(
) -> BookmakerAdapterRegistry:
    registry = (
        BookmakerAdapterRegistry()
    )

    registry.register(
        PaddyPowerAdapter()
    )
    registry.register(
        Bet365Adapter()
    )

    return registry
