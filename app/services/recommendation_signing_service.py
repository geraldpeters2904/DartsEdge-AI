import base64
import hashlib
import hmac
import json
import math
import os
import time


SIGNING_KEY_ENV = "DARTSEDGE_RECOMMENDATION_SIGNING_KEY"
TOKEN_LIFETIME_SECONDS = 900


def _encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        value + padding,
        altchars=b"-_",
        validate=True,
    )


def _secret():
    value = os.getenv(SIGNING_KEY_ENV, "")
    if not value or len(value.encode("utf-8")) < 32:
        return None
    return value.encode("utf-8")


def sign_recommendation(
    *,
    fixture_id,
    market,
    selection,
    odds,
    effective_stake,
):
    secret = _secret()
    if secret is None:
        return None

    try:
        fixture_id = int(fixture_id)
        odds = float(odds)
        effective_stake = float(effective_stake)

        if (
            fixture_id <= 0
            or not math.isfinite(odds)
            or odds <= 1
            or not math.isfinite(effective_stake)
            or effective_stake <= 0
            or not str(market).strip()
            or not str(selection).strip()
        ):
            return None

        payload = {
            "fixture_id": fixture_id,
            "market": str(market),
            "selection": str(selection),
            "odds": odds,
            "effective_stake": effective_stake,
            "issued_at": int(time.time()),
        }

        encoded = _encode(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )

        signature = _encode(
            hmac.new(
                secret,
                encoded.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )

        return f"{encoded}.{signature}"

    except (TypeError, ValueError, OverflowError):
        return None


def verify_recommendation(token):
    secret = _secret()
    if secret is None or not isinstance(token, str):
        return None

    try:
        encoded, signature = token.split(".")

        expected = hmac.new(
            secret,
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(_decode(signature), expected):
            return None

        payload = json.loads(_decode(encoded))

        if not isinstance(payload, dict):
            return None

        issued_at = payload["issued_at"]
        now = time.time()

        if type(issued_at) is not int:
            return None

        if issued_at > now or now - issued_at > TOKEN_LIFETIME_SECONDS:
            return None

        fixture_id = payload["fixture_id"]
        odds = payload["odds"]
        stake = payload["effective_stake"]

        if (
            type(fixture_id) is not int
            or fixture_id <= 0
            or type(odds) not in (int, float)
            or not math.isfinite(odds)
            or odds <= 1
            or type(stake) not in (int, float)
            or not math.isfinite(stake)
            or stake <= 0
            or not isinstance(payload["market"], str)
            or not payload["market"].strip()
            or not isinstance(payload["selection"], str)
            or not payload["selection"].strip()
        ):
            return None

        return payload

    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        OverflowError,
    ):
        return None
