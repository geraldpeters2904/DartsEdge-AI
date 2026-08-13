from __future__ import annotations

import os
import subprocess


KEYCHAIN_SERVICE = "DartsEdgeMobile"
MOBILE_USERNAME = os.getenv(
    "DARTSEDGE_MOBILE_USERNAME",
    "gerald",
)


def keychain_password() -> str:
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-a",
            MOBILE_USERNAME,
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "DartsEdge mobile password was not found "
            "in macOS Keychain."
        )

    password = result.stdout.rstrip("\n")

    if not password:
        raise RuntimeError(
            "DartsEdge mobile password in macOS Keychain is blank."
        )

    return password


def main() -> None:
    env = os.environ.copy()
    env["DARTSEDGE_MOBILE_USERNAME"] = MOBILE_USERNAME
    env["DARTSEDGE_MOBILE_PASSWORD"] = keychain_password()
    env["PYTHONUNBUFFERED"] = "1"

    python_path = (
        "/Users/geraldpeters/dartsedge-ai/"
        "backend/venv/bin/python"
    )

    argv = [
        python_path,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]

    os.execvpe(
        python_path,
        argv,
        env,
    )


if __name__ == "__main__":
    main()
