from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


CONFIG_FILENAME = ".historical_capture_config.json"

SUPPORTED_PROVIDERS = {
    "manual",
    "safari",
    "chrome",
}


@dataclass(frozen=True)
class HistoricalCaptureConfig:
    provider: str = "manual"
    browser_timeout_seconds: float = 30.0
    delay_between_captures_seconds: float = 3.0
    retry_limit: int = 3
    retry_delay_seconds: float = 5.0
    stop_on_access_challenge: bool = True

    def validate(self) -> None:
        provider = self.provider.strip().casefold()

        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported capture provider: {self.provider!r}. "
                "Expected manual, safari or chrome."
            )

        if self.browser_timeout_seconds <= 0:
            raise ValueError(
                "Browser timeout must be greater than zero."
            )

        if self.delay_between_captures_seconds < 0:
            raise ValueError(
                "Capture delay cannot be negative."
            )

        if self.retry_limit < 0:
            raise ValueError(
                "Retry limit cannot be negative."
            )

        if self.retry_delay_seconds < 0:
            raise ValueError(
                "Retry delay cannot be negative."
            )


class HistoricalCaptureConfigService:
    """Persist capture-runner configuration below the batch root."""

    def load(
        self,
        root: str | Path,
    ) -> HistoricalCaptureConfig:
        root_path = self._normalise_root(root)
        path = root_path / CONFIG_FILENAME

        if not path.is_file():
            return HistoricalCaptureConfig()

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                "Historical capture configuration is invalid: "
                + str(exc)
            ) from exc

        config = HistoricalCaptureConfig(
            provider=str(
                payload.get("provider", "manual")
            ).strip().casefold(),
            browser_timeout_seconds=float(
                payload.get(
                    "browser_timeout_seconds",
                    30.0,
                )
            ),
            delay_between_captures_seconds=float(
                payload.get(
                    "delay_between_captures_seconds",
                    3.0,
                )
            ),
            retry_limit=int(
                payload.get("retry_limit", 3)
            ),
            retry_delay_seconds=float(
                payload.get(
                    "retry_delay_seconds",
                    5.0,
                )
            ),
            stop_on_access_challenge=bool(
                payload.get(
                    "stop_on_access_challenge",
                    True,
                )
            ),
        )

        config.validate()
        return config

    def save(
        self,
        root: str | Path,
        config: HistoricalCaptureConfig,
    ) -> HistoricalCaptureConfig:
        root_path = self._normalise_root(root)

        normalised = HistoricalCaptureConfig(
            provider=config.provider.strip().casefold(),
            browser_timeout_seconds=(
                config.browser_timeout_seconds
            ),
            delay_between_captures_seconds=(
                config.delay_between_captures_seconds
            ),
            retry_limit=config.retry_limit,
            retry_delay_seconds=(
                config.retry_delay_seconds
            ),
            stop_on_access_challenge=(
                config.stop_on_access_challenge
            ),
        )

        normalised.validate()
        root_path.mkdir(parents=True, exist_ok=True)

        temporary = root_path / (
            CONFIG_FILENAME + ".part"
        )
        destination = root_path / CONFIG_FILENAME

        temporary.write_text(
            json.dumps(
                asdict(normalised),
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(destination)

        return normalised

    def clear(
        self,
        root: str | Path,
    ) -> bool:
        path = (
            self._normalise_root(root)
            / CONFIG_FILENAME
        )

        if not path.exists():
            return False

        path.unlink()
        return True

    @staticmethod
    def _normalise_root(
        value: str | Path,
    ) -> Path:
        text = str(value or "").strip()

        if not text:
            raise ValueError(
                "Enter a historical capture root."
            )

        return Path(text).expanduser().resolve()
