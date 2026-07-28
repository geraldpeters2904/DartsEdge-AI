from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ModusConnectorPolicy:
    """
    Safety gate for any live automated access.

    Browser-assisted parsing remains available regardless of this flag.
    """

    enabled: bool = False
    permission_confirmed: bool = False
    minimum_interval_seconds: float = 5.0
    max_matches_per_run: int = 50
    cache_ttl_hours: int = 168

    @classmethod
    def from_environment(cls) -> "ModusConnectorPolicy":
        return cls(
            enabled=_env_bool("DARTSEDGE_MODUS_CONNECTOR_ENABLED", False),
            permission_confirmed=_env_bool(
                "DARTSEDGE_MODUS_PERMISSION_CONFIRMED",
                False,
            ),
            minimum_interval_seconds=_env_float(
                "DARTSEDGE_MODUS_MIN_REQUEST_INTERVAL_SECONDS",
                5.0,
            ),
            max_matches_per_run=_env_int(
                "DARTSEDGE_MODUS_MAX_MATCHES_PER_RUN",
                50,
            ),
            cache_ttl_hours=_env_int(
                "DARTSEDGE_MODUS_CACHE_TTL_HOURS",
                168,
            ),
        )

    @property
    def automation_allowed(self) -> bool:
        return self.enabled and self.permission_confirmed

    def assert_automation_allowed(self) -> None:
        if not self.enabled:
            raise RuntimeError(
                "Automated MODUS retrieval is disabled. "
                "Use browser-assisted mode."
            )
        if not self.permission_confirmed:
            raise RuntimeError(
                "Automated MODUS retrieval requires documented permission."
            )
        if self.minimum_interval_seconds < 1.0:
            raise RuntimeError(
                "The MODUS request interval must be at least one second."
            )
        if self.max_matches_per_run <= 0:
            raise RuntimeError(
                "The MODUS per-run match limit must be positive."
            )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None else float(raw)
