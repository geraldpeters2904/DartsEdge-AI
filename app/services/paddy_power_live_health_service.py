from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
    resolve_capture_callable,
)


@dataclass(frozen=True)
class PaddyPowerLiveHealth:
    ready: bool
    module_name: Optional[str]
    function_name: Optional[str]
    message: str
    error: Optional[str] = None


def check_paddy_power_live_health(
) -> PaddyPowerLiveHealth:
    try:
        resolution = (
            resolve_capture_callable()
        )

        return PaddyPowerLiveHealth(
            ready=True,
            module_name=(
                resolution.module_name
            ),
            function_name=(
                resolution.function_name
            ),
            message=(
                "Paddy Power live bridge is ready."
            ),
        )

    except Exception as exc:
        return PaddyPowerLiveHealth(
            ready=False,
            module_name=None,
            function_name=None,
            message=(
                "Paddy Power live bridge is not ready."
            ),
            error=str(exc),
        )
