#!/Users/geraldpeters/dartsedge-ai/backend/venv/bin/python

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen


HEALTH_URL = "http://127.0.0.1:8000/health"

LOG_PATH = Path(
    "/Users/geraldpeters/Library/Logs/DartsEdge/watchdog.log"
)

STATE_PATH = Path(
    "/Users/geraldpeters/Library/Logs/DartsEdge/watchdog-state.json"
)

SERVICE_LABEL = "com.dartsedge.api"

FAILURES_BEFORE_RESTART = 2
RESTART_COOLDOWN_SECONDS = 15 * 60


def log(message: str) -> None:
    timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            f"{timestamp} | {message}\n"
        )


def load_state():
    if not STATE_PATH.exists():
        return {
            "consecutive_failures": 0,
            "last_restart_at": None,
        }

    try:
        return json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {
            "consecutive_failures": 0,
            "last_restart_at": None,
        }


def save_state(state):
    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_PATH.write_text(
        json.dumps(
            state,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def restart_allowed(state) -> bool:
    last_restart = state.get(
        "last_restart_at"
    )

    if last_restart is None:
        return True

    return (
        time.time()
        - float(last_restart)
        >= RESTART_COOLDOWN_SECONDS
    )


def restart_dartsedge(
    state,
    *,
    reason,
):
    if not restart_allowed(state):
        remaining = (
            RESTART_COOLDOWN_SECONDS
            - (
                time.time()
                - float(
                    state["last_restart_at"]
                )
            )
        )

        log(
            "RESTART_SUPPRESSED | "
            f"cooldown_remaining={max(0, int(remaining))}s | "
            f"reason={reason}"
        )

        return False

    domain = (
        f"gui/{os.getuid()}/"
        f"{SERVICE_LABEL}"
    )

    try:
        result = subprocess.run(
            [
                "/bin/launchctl",
                "kickstart",
                "-k",
                domain,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            plist = (
                "/Users/geraldpeters/Library/"
                "LaunchAgents/com.dartsedge.api.plist"
            )

            bootstrap = subprocess.run(
                [
                    "/bin/launchctl",
                    "bootstrap",
                    f"gui/{os.getuid()}",
                    plist,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if bootstrap.returncode != 0:
                log(
                    "RESTART_FAILED | "
                    f"kickstart={result.stderr.strip()} | "
                    f"bootstrap={bootstrap.stderr.strip()}"
                )
                return False

            log(
                "SERVICE_BOOTSTRAPPED | "
                f"reason={reason}"
            )

    except Exception as exc:
        log(
            "RESTART_FAILED | "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    state["last_restart_at"] = (
        time.time()
    )
    state["consecutive_failures"] = 0

    save_state(state)

    log(
        "RESTARTED_DARTSEDGE | "
        f"reason={reason}"
    )

    return True


def health_payload():
    with urlopen(
        HEALTH_URL,
        timeout=15,
    ) as response:
        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def evaluate_health(payload):
    monitors = payload.get(
        "monitors",
        {},
    )

    forward = monitors.get(
        "forward_schedule",
        {},
    )

    live_edge = monitors.get(
        "live_edge",
        {},
    )

    problems = []

    if not forward.get(
        "healthy",
        False,
    ):
        problems.append(
            "FORWARD_MONITOR_UNHEALTHY"
        )

    if not live_edge.get(
        "healthy",
        False,
    ):
        problems.append(
            "LIVE_EDGE_MONITOR_UNHEALTHY"
        )

    if payload.get("status") not in {
        "healthy",
        "ok",
    }:
        problems.append(
            "APPLICATION_DEGRADED"
        )

    return (
        problems,
        forward,
        live_edge,
    )


def record_failure(
    state,
    *,
    reason,
):
    state["consecutive_failures"] = (
        int(
            state.get(
                "consecutive_failures",
                0,
            )
        )
        + 1
    )

    save_state(state)

    log(
        "UNHEALTHY | "
        f"consecutive_failures="
        f"{state['consecutive_failures']} | "
        f"reason={reason}"
    )

    if (
        state["consecutive_failures"]
        >= FAILURES_BEFORE_RESTART
    ):
        restart_dartsedge(
            state,
            reason=reason,
        )


def main() -> int:
    state = load_state()

    try:
        payload = health_payload()

    except Exception as exc:
        reason = (
            "API_UNREACHABLE | "
            f"{type(exc).__name__}: {exc}"
        )

        record_failure(
            state,
            reason=reason,
        )

        return 1

    problems, forward, live_edge = (
        evaluate_health(payload)
    )

    if problems:
        record_failure(
            state,
            reason=",".join(problems),
        )

        return 1

    if (
        state.get(
            "consecutive_failures",
            0,
        )
        != 0
    ):
        log(
            "RECOVERED_WITHOUT_RESTART | "
            f"previous_failures="
            f"{state['consecutive_failures']}"
        )

    state["consecutive_failures"] = 0
    save_state(state)

    log(
        "HEALTHY | "
        f"forward_runs="
        f"{forward.get('runs')} | "
        f"live_edge_runs="
        f"{live_edge.get('runs')}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
