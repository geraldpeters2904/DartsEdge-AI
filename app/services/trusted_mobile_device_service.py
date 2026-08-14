from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

TRUSTED_DEVICE_COOKIE_NAME = "dartsedge_trusted_device"
TRUSTED_DEVICE_DAYS = 30

DEFAULT_TRUSTED_DEVICE_STATE_PATH = Path(
    "/Users/geraldpeters/Library/Logs/"
    "DartsEdge/trusted-mobile-devices.json"
)


def _state_path() -> Path:
    override = os.getenv(
        "DARTSEDGE_TRUSTED_DEVICE_STATE",
        "",
    ).strip()

    return (
        Path(override)
        if override
        else DEFAULT_TRUSTED_DEVICE_STATE_PATH
    )


def _digest(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def _load() -> dict:
    path = _state_path()

    if not path.exists():
        return {"devices": []}

    try:
        payload = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return {"devices": []}

    devices = payload.get("devices")

    if not isinstance(devices, list):
        return {"devices": []}

    return {"devices": devices}


def _save(payload: dict) -> None:
    path = _state_path()
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    temporary.replace(path)


def _prune(
    payload: dict,
    *,
    now: datetime,
) -> bool:
    retained = []

    for device in payload.get(
        "devices",
        [],
    ):
        try:
            expires_at = datetime.fromisoformat(
                str(device["expires_at"])
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            continue

        if expires_at > now:
            retained.append(device)

    changed = (
        retained
        != payload.get("devices", [])
    )

    payload["devices"] = retained
    return changed


def create_trusted_device(
    *,
    now: Optional[datetime] = None,
    days: int = TRUSTED_DEVICE_DAYS,
) -> str:
    current = now or datetime.utcnow()
    lifetime = max(
        1,
        min(int(days), 365),
    )

    token = secrets.token_urlsafe(48)

    payload = _load()
    _prune(
        payload,
        now=current,
    )

    payload["devices"].append({
        "token_sha256": _digest(token),
        "created_at": current.isoformat(),
        "expires_at": (
            current
            + timedelta(days=lifetime)
        ).isoformat(),
    })

    _save(payload)
    return token


def valid_trusted_device(
    token: Optional[str],
    *,
    now: Optional[datetime] = None,
) -> bool:
    candidate = str(token or "")

    if not candidate:
        return False

    current = now or datetime.utcnow()
    payload = _load()

    changed = _prune(
        payload,
        now=current,
    )

    candidate_digest = _digest(
        candidate
    )

    valid = any(
        secrets.compare_digest(
            candidate_digest,
            str(
                device.get(
                    "token_sha256",
                    "",
                )
            ),
        )
        for device in payload["devices"]
    )

    if changed:
        _save(payload)

    return valid


def revoke_trusted_device(
    token: Optional[str],
) -> bool:
    candidate = str(token or "")

    if not candidate:
        return False

    candidate_digest = _digest(
        candidate
    )

    payload = _load()
    original = list(
        payload["devices"]
    )

    payload["devices"] = [
        device
        for device in original
        if not secrets.compare_digest(
            candidate_digest,
            str(
                device.get(
                    "token_sha256",
                    "",
                )
            ),
        )
    ]

    changed = (
        payload["devices"]
        != original
    )

    if changed:
        _save(payload)

    return changed


def revoke_all_trusted_devices() -> int:
    payload = _load()
    count = len(
        payload["devices"]
    )

    _save({
        "devices": [],
    })

    return count


def trusted_device_count(
    *,
    now: Optional[datetime] = None,
) -> int:
    current = now or datetime.utcnow()
    payload = _load()

    if _prune(
        payload,
        now=current,
    ):
        _save(payload)

    return len(
        payload["devices"]
    )
