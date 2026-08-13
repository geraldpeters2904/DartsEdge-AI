from __future__ import annotations

import socket

from app.services.mobile_access_service import (
    PAIRING_TTL_SECONDS,
    create_mobile_pairing_token,
)


def _local_ip() -> str:
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    try:
        sock.connect(
            (
                "8.8.8.8",
                80,
            )
        )

        return str(
            sock.getsockname()[0]
        )

    finally:
        sock.close()


def main() -> None:
    token = (
        create_mobile_pairing_token()
    )

    host = _local_ip()

    print()
    print(
        "DARTSEDGE MOBILE PAIRING"
    )
    print(
        "=" * 70
    )
    print(
        "Open this address on the iPhone/iPad:"
    )
    print()
    print(
        f"http://{host}:8000/mobile-pair/{token}"
    )
    print()
    print(
        "This link is single-use and expires in "
        f"{PAIRING_TTL_SECONDS // 60} minutes."
    )


if __name__ == "__main__":
    main()
