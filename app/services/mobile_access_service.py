from __future__ import annotations

import hashlib
import os
import secrets
from typing import Optional


COOKIE_NAME = "dartsedge_mobile_session"
COOKIE_SALT = "dartsedge-mobile-session-v1"


def configured_mobile_credentials() -> tuple[str, str]:
    username = os.getenv(
        "DARTSEDGE_MOBILE_USERNAME",
        "",
    )
    password = os.getenv(
        "DARTSEDGE_MOBILE_PASSWORD",
        "",
    )

    return username, password


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

    username_ok = secrets.compare_digest(
        str(username),
        expected_username,
    )

    password_ok = secrets.compare_digest(
        str(password),
        expected_password,
    )

    return bool(
        username_ok
        and password_ok
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
