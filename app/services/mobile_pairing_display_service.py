from __future__ import annotations

import base64
import io
import os
import socket
from dataclasses import dataclass

from app.services.mobile_access_service import (
    PAIRING_TTL_SECONDS,
    create_mobile_pairing_token,
)

DEFAULT_HTTPS_BASE_URL = (
    "https://geralds-imac.tail74e2bd.ts.net"
)

@dataclass(frozen=True)
class MobilePairingDisplay:
    pairing_url: str
    qr_data_uri: str
    expires_minutes: int

def local_network_ip() -> str:
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    finally:
        sock.close()

def mobile_base_url() -> str:
    configured = os.getenv(
        "DARTSEDGE_MOBILE_BASE_URL",
        "",
    ).strip()

    if configured:
        return configured.rstrip("/")

    if DEFAULT_HTTPS_BASE_URL:
        return DEFAULT_HTTPS_BASE_URL

    return f"http://{local_network_ip()}:8000"

def build_mobile_pairing_display() -> MobilePairingDisplay:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError(
            "QR support requires the Python 'qrcode' package."
        ) from exc

    token = create_mobile_pairing_token()

    pairing_url = (
        f"{mobile_base_url()}/"
        f"mobile-pair/{token}"
    )

    image = qrcode.make(pairing_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    encoded = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return MobilePairingDisplay(
        pairing_url=pairing_url,
        qr_data_uri=(
            "data:image/png;base64,"
            + encoded
        ),
        expires_minutes=(
            PAIRING_TTL_SECONDS // 60
        ),
    )
