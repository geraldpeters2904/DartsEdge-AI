from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

COOKIE_NAME = "dartsedge_mobile_session"
COOKIE_SALT = "dartsedge-mobile-session-v1"
PAIRING_TTL_SECONDS = 600

DEFAULT_PAIRING_STATE_PATH = Path(
    "/Users/geraldpeters/Library/Logs/"
    "DartsEdge/mobile-pairing.json"
)


def _pairing_state_path() -> Path:
    override = os.getenv(
        "DARTSEDGE_MOBILE_PAIRING_STATE",
        "",
    ).strip()

    return (
        Path(override)
        if override
        else DEFAULT_PAIRING_STATE_PATH
    )


def configured_mobile_credentials() -> tuple[str, str]:
    return (
        os.getenv(
            "DARTSEDGE_MOBILE_USERNAME",
            "",
        ),
        os.getenv(
            "DARTSEDGE_MOBILE_PASSWORD",
            "",
        ),
    )


def mobile_access_configured() -> bool:
    username, password = (
        configured_mobile_credentials()
    )

    return bool(
        username
        and password
    )


def validate_mobile_credentials(
    *,
    username: str,
    password: str,
) -> bool:
    expected_username, expected_password = (
        configured_mobile_credentials()
    )

    if not (
        expected_username
        and expected_password
    ):
        return False

    return bool(
        secrets.compare_digest(
            str(username),
            expected_username,
        )
        and secrets.compare_digest(
            str(password),
            expected_password,
        )
    )


def mobile_session_token() -> Optional[str]:
    username, password = (
        configured_mobile_credentials()
    )

    if not (
        username
        and password
    ):
        return None

    payload = (
        f"{COOKIE_SALT}\0"
        f"{username}\0"
        f"{password}"
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        payload
    ).hexdigest()


def valid_mobile_session(
    value: Optional[str],
) -> bool:
    expected = mobile_session_token()

    if not (
        expected
        and value
    ):
        return False

    return secrets.compare_digest(
        str(value),
        expected,
    )


def _token_digest(
    token: str,
) -> str:
    return hashlib.sha256(
        str(token).encode(
            "utf-8"
        )
    ).hexdigest()


def _write_pairing_state(
    payload: dict,
) -> None:
    path = _pairing_state_path()

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

    temporary.replace(
        path
    )


def _read_pairing_state() -> Optional[dict]:
    path = _pairing_state_path()

    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None


def clear_mobile_pairing_token() -> None:
    path = _pairing_state_path()

    try:
        path.unlink()
    except FileNotFoundError:
        pass


def create_mobile_pairing_token(
    *,
    now: Optional[datetime] = None,
    ttl_seconds: int = PAIRING_TTL_SECONDS,
) -> str:
    current = (
        now
        or datetime.utcnow()
    )

    ttl = max(
        60,
        min(
            int(ttl_seconds),
            3600,
        ),
    )

    token = secrets.token_urlsafe(
        32
    )

    expires_at = (
        current
        + timedelta(
            seconds=ttl
        )
    )

    _write_pairing_state({
        "token_sha256": (
            _token_digest(
                token
            )
        ),
        "created_at": (
            current.isoformat()
        ),
        "expires_at": (
            expires_at.isoformat()
        ),
    })

    return token


def consume_mobile_pairing_token(
    token: str,
    *,
    now: Optional[datetime] = None,
) -> bool:
    candidate = str(
        token
        or ""
    )

    if not candidate:
        return False

    state = _read_pairing_state()

    if not state:
        return False

    current = (
        now
        or datetime.utcnow()
    )

    try:
        expires_at = datetime.fromisoformat(
            str(
                state[
                    "expires_at"
                ]
            )
        )

        expected_digest = str(
            state[
                "token_sha256"
            ]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        clear_mobile_pairing_token()
        return False

    if current >= expires_at:
        clear_mobile_pairing_token()
        return False

    candidate_digest = (
        _token_digest(
            candidate
        )
    )

    if not secrets.compare_digest(
        candidate_digest,
        expected_digest,
    ):
        return False

    clear_mobile_pairing_token()

    return True
