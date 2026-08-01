from __future__ import annotations

from typing import Callable, Protocol


class BrowserSession(Protocol):
    """Reusable browser session used by capture providers."""

    @property
    def running(self) -> bool:
        ...

    def open(self) -> None:
        """Start the browser session if it is not already running."""
        ...

    def goto(
        self,
        url: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Navigate to a webpage and wait for it to become ready."""
        ...

    def wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_seconds: float = 30.0,
        description: str = "browser condition",
    ) -> None:
        """Wait until a supplied browser condition returns True."""
        ...

    def html(self) -> str:
        """Return the current rendered HTML document."""
        ...

    def title(self) -> str:
        """Return the current page title."""
        ...

    def current_url(self) -> str:
        """Return the current browser URL."""
        ...

    def close(self) -> None:
        """Close the browser session safely."""
        ...
