from __future__ import annotations

import atexit
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
        self._atexit_registered = False

    @property
    def running(self) -> bool:
        return self._driver is not None

    @property
    def profile_path(self) -> Optional[Path]:
        return self._profile_path

    def open(self) -> None:
        if self.running:
            return

        first_error = None

        try:
            driver = (
                self._driver_factory()
                if self._driver_factory is not None
                else self._create_chrome_driver()
            )
        except Exception as exc:
            first_error = exc
            self._cleanup_profile()

            if (
                self._driver_factory is None
                and self._headless
            ):
                raise RuntimeError(
                    "Could not start dedicated Chrome automation "
                    "in headless mode. Visible fallback is disabled "
                    "so automated collection cannot steal desktop focus. "
                    f"Headless error: {first_error}"
                ) from exc

            raise RuntimeError(
                "Could not start dedicated Chrome automation: "
                + str(exc)
            ) from exc

        self._driver = driver

        if not self._atexit_registered:
            atexit.register(self.close)
            self._atexit_registered = True

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
                driver.set_page_load_timeout(
                    float(timeout_seconds)
                )
                driver.get(target)
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

    def html(self) -> str:
        return str(
            self._require_driver().page_source
            or ""
        )

    def title(self) -> str:
        return str(
            self._require_driver().title
            or ""
        )

    def current_url(self) -> str:
        return str(
            self._require_driver().current_url
            or ""
        )

    def wait_for(
        self,
        predicate: Callable[[], bool],
        *,
        timeout_seconds: float = 30.0,
        description: str = "browser condition",
    ) -> None:
        deadline = (
            time.monotonic()
            + float(timeout_seconds)
        )

        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except Exception:
                pass

            time.sleep(
                self._poll_interval_seconds
            )

        raise TimeoutError(
            f"Timed out waiting for {description}."
        )

    def close(self) -> None:
        driver = self._driver
        self._driver = None

        service_process = None

        if driver is not None:
            try:
                service = getattr(
                    driver,
                    "service",
                    None,
                )
                service_process = getattr(
                    service,
                    "process",
                    None,
                )
            except Exception:
                service_process = None

            try:
                driver.quit()
            except Exception:
                pass

        if service_process is not None:
            try:
                if service_process.poll() is None:
                    service_process.terminate()
                    try:
                        service_process.wait(
                            timeout=2.0
                        )
                    except Exception:
                        service_process.kill()
            except Exception:
                pass

        self._cleanup_profile()

    def _require_driver(self):
        if self._driver is None:
            raise RuntimeError(
                "Chrome browser session is not open."
            )

        return self._driver

    @staticmethod
    def _session_is_lost(
        exc: Exception,
    ) -> bool:
        message = str(exc).casefold()

        markers = (
            "invalid session id",
            "chrome not reachable",
            "disconnected",
            "not connected to devtools",
            "timed out receiving message from renderer",
        )

        return any(
            marker in message
            for marker in markers
        )

    def _cleanup_profile(self) -> None:
        profile = self._profile_path
        self._profile_path = None

        if (
            profile is not None
            and profile.exists()
        ):
            shutil.rmtree(
                profile,
                ignore_errors=True,
            )

    def _create_chrome_driver(self):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import (
                Options,
            )
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

        return webdriver.Chrome(
            options=options
        )

    def _create_profile_path(self) -> Path:
        if self._configured_profile_root is not None:
            self._configured_profile_root.mkdir(
                parents=True,
                exist_ok=True,
            )
            profile = Path(
                tempfile.mkdtemp(
                    prefix="dartsedge-chrome-",
                    dir=str(
                        self._configured_profile_root
                    ),
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

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None
