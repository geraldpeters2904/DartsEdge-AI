from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Optional


class ChromeBrowserSession:
    """
    Reusable Selenium Chrome session with its own isolated browser profile.

    The temporary profile prevents DartsEdge automation from sharing cookies,
    tabs, extensions, locks, or WebDriver state with the user's normal browser.
    Safari remains completely independent and can be used normally.
    """

    def __init__(
        self,
        *,
        driver_factory: Optional[Callable[[], Any]] = None,
        poll_interval_seconds: float = 0.2,
        headless: bool = False,
        profile_root: Optional[str | Path] = None,
    ) -> None:
        self._driver_factory = driver_factory
        self._poll_interval_seconds = max(
            float(poll_interval_seconds),
            0.05,
        )
        self._headless = bool(headless)
        self._configured_profile_root = (
            Path(profile_root).expanduser().resolve()
            if profile_root is not None
            else None
        )
        self._profile_path: Optional[Path] = None
        self._driver: Optional[Any] = None

    @property
    def running(self) -> bool:
        return self._driver is not None

    @property
    def profile_path(self) -> Optional[Path]:
        return self._profile_path

    def open(self) -> None:
        if self.running:
            return

        try:
            driver = (
                self._driver_factory()
                if self._driver_factory is not None
                else self._create_chrome_driver()
            )
        except Exception as exc:
            self._cleanup_profile()
            raise RuntimeError(
                "Could not start dedicated Chrome automation: "
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

        first_error = None

        for attempt in range(2):
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
                return

            except Exception as exc:
                if first_error is None:
                    first_error = exc

                if attempt == 0 and self._session_is_lost(exc):
                    self.close()
                    continue

                raise RuntimeError(
                    f"Dedicated Chrome could not load {target}: {exc}"
                ) from exc

        raise RuntimeError(
            f"Dedicated Chrome could not load {target}: {first_error}"
        )

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
            f"Dedicated Chrome did not satisfy {description} "
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
                "Dedicated Chrome returned an empty HTML document."
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

        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

        self._cleanup_profile()

    @staticmethod
    def _session_is_lost(exc: Exception) -> bool:
        message = str(exc or "").casefold()

        return any(
            marker in message
            for marker in (
                "invalid session id",
                "session deleted",
                "browser has closed the connection",
                "not connected to devtools",
                "disconnected",
                "chrome not reachable",
                "target window already closed",
                "timed out receiving message from renderer",
                "timeout: timed out receiving message",
                "renderer timeout",
            )
        )

    def _require_driver(self):
        if self._driver is None:
            raise RuntimeError(
                "Dedicated Chrome browser session is not running."
            )

        return self._driver

    def _create_chrome_driver(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError(
                "Selenium is not installed. Run: "
                "python -m pip install selenium"
            ) from exc

        profile_path = self._create_profile_path()
        options = Options()
        options.add_argument(
            f"--user-data-dir={profile_path}"
        )
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--window-size=1280,1000")

        if self._headless:
            options.add_argument("--headless=new")

        binary = self._find_chrome_binary()

        if binary is not None:
            options.binary_location = str(binary)

        # Selenium Manager resolves a compatible ChromeDriver automatically.
        return webdriver.Chrome(options=options)

    def _create_profile_path(self) -> Path:
        if self._configured_profile_root is not None:
            self._configured_profile_root.mkdir(
                parents=True,
                exist_ok=True,
            )
            profile = Path(
                tempfile.mkdtemp(
                    prefix="dartsedge-chrome-",
                    dir=str(self._configured_profile_root),
                )
            )
        else:
            profile = Path(
                tempfile.mkdtemp(
                    prefix="dartsedge-chrome-"
                )
            )

        self._profile_path = profile
        return profile

    @staticmethod
    def _find_chrome_binary() -> Optional[Path]:
        candidates = (
            Path(
                "/Applications/Google Chrome.app/"
                "Contents/MacOS/Google Chrome"
            ),
            Path(
                "/Applications/Google Chrome Beta.app/"
                "Contents/MacOS/Google Chrome Beta"
            ),
            Path(
                "/Applications/Chromium.app/"
                "Contents/MacOS/Chromium"
            ),
        )

        return next(
            (
                path
                for path in candidates
                if path.is_file()
            ),
            None,
        )

    def _cleanup_profile(self) -> None:
        profile = self._profile_path
        self._profile_path = None

        if profile is None:
            return

        shutil.rmtree(
            profile,
            ignore_errors=True,
        )

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
