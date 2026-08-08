from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.paddy_power_live_capture import (
    build_paddy_power_capture_once,
)
from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
)


@dataclass(frozen=True)
class PaddyPowerLiveHealth:
    ready: bool
    module_name: Optional[str]
    function_name: Optional[str]
    message: str
    error: Optional[str] = None


def resolve_capture_callable(
) -> PaddyPowerBridgeResolution:
    """
    Local compatibility wrapper.

    Older tests patch this name directly.
    Newer tests patch build_paddy_power_capture_once directly.
    Both therefore exercise the same health-check path.
    """
    capture_once, service = (
        build_paddy_power_capture_once()
    )

    try:
        if not callable(
            capture_once
        ):
            raise TypeError(
                "build_paddy_power_capture_once() did not return "
                "a callable capture function."
            )

        return PaddyPowerBridgeResolution(
            module_name=(
                "app.services.paddy_power_live_capture"
            ),
            function_name=(
                "build_paddy_power_capture_once"
            ),
            callable=capture_once,
        )

    finally:
        service.close()


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
            error=str(
                exc
            ),
        )
