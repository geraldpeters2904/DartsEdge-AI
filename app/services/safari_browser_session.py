from __future__ import annotations

import time
from typing import Any, Callable, Optional


class SafariBrowserSession:
    """Reusable Selenium Safari WebDriver session."""

    def __init__(
        self,
        *,
        driver_factory: Optional[Callable[[], Any]] = None,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self._driver_factory = driver_factory
        self._poll_interval_seconds = poll_interval_seconds
        self._driver: Optional[Any] = None

    @property
    def running(self) -> bool:
        return self._driver is not None

    def open(self) -> None:
        if self.running:
            return

        try:
            driver = (
                self._driver_factory()
                if self._driver_factory is not None
                else self._create_safari_driver()
            )
        except Exception as exc:
            raise RuntimeError(
                "Could not start Safari automation: "
                + str(exc)
            ) from exc

        self._driver = driver

    def goto(
        self,
        url: str,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        target = str(url or "").strip()

        if not target:
            raise ValueError("Enter a browser destination URL.")

        if not target.startswith(("http://", "https://")):
            raise ValueError(
                "Browser destination must use HTTP or HTTPS."
            )

        self.open()
        driver = self._require_driver()

        try:
            driver.set_page_load_timeout(timeout_seconds)
            driver.get(target)

            self.wait_for(
                lambda: (
                    driver.execute_script(
                        "return document.readyState"
                    )
                    == "complete"
                ),
                timeout_seconds=timeout_seconds,
                description="document.readyState=complete",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Safari could not load {target}: {exc}"
            ) from exc

    def wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_seconds: float = 30.0,
        description: str = "browser condition",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Browser wait timeout must be positive."
            )

        deadline = time.monotonic() + timeout_seconds
        last_error: Optional[Exception] = None

        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except Exception as exc:
                last_error = exc

            time.sleep(self._poll_interval_seconds)

        message = (
            f"Safari did not satisfy {description} "
            f"within {timeout_seconds:.1f} seconds."
        )

        if last_error is not None:
            message += f" Last error: {last_error}"

        raise TimeoutError(message)

    def html(self) -> str:
        driver = self._require_driver()
        html = str(driver.page_source or "")

        if not html.strip():
            raise RuntimeError(
                "Safari returned an empty HTML document."
            )

        return html

    def title(self) -> str:
        driver = self._require_driver()
        return str(driver.title or "")

    def current_url(self) -> str:
        driver = self._require_driver()
        return str(driver.current_url or "")

    def close(self) -> None:
        driver = self._driver
        self._driver = None

        if driver is None:
            return

        try:
            driver.quit()
        except Exception:
            pass

    def _require_driver(self):
        if self._driver is None:
            raise RuntimeError(
                "Safari browser session is not running."
            )

        return self._driver

    @staticmethod
    def _create_safari_driver():
        try:
            from selenium import webdriver
        except ImportError as exc:
            raise RuntimeError(
                "Selenium is not installed. Run: "
                "python -m pip install selenium"
            ) from exc

        return webdriver.Safari()

    def __enter__(self):
        self.open()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()
