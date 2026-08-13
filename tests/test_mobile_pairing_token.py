import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.services.mobile_access_service import (
    clear_mobile_pairing_token,
    consume_mobile_pairing_token,
    create_mobile_pairing_token,
)


class MobilePairingTokenTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.state_path = (
            Path(
                self.tempdir.name
            )
            / "pairing.json"
        )

        self.env = patch.dict(
            os.environ,
            {
                "DARTSEDGE_MOBILE_PAIRING_STATE": (
                    str(
                        self.state_path
                    )
                )
            },
        )

        self.env.start()

        clear_mobile_pairing_token()

    def tearDown(self):
        clear_mobile_pairing_token()
        self.env.stop()
        self.tempdir.cleanup()

    def test_valid_token_is_single_use(self):
        now = datetime(
            2026,
            8,
            13,
            15,
            0,
            0,
        )

        token = (
            create_mobile_pairing_token(
                now=now,
                ttl_seconds=600,
            )
        )

        self.assertTrue(
            consume_mobile_pairing_token(
                token,
                now=(
                    now
                    + timedelta(
                        minutes=1
                    )
                ),
            )
        )

        self.assertFalse(
            consume_mobile_pairing_token(
                token,
                now=(
                    now
                    + timedelta(
                        minutes=2
                    )
                ),
            )
        )

    def test_expired_token_is_rejected(self):
        now = datetime(
            2026,
            8,
            13,
            15,
            0,
            0,
        )

        token = (
            create_mobile_pairing_token(
                now=now,
                ttl_seconds=600,
            )
        )

        self.assertFalse(
            consume_mobile_pairing_token(
                token,
                now=(
                    now
                    + timedelta(
                        minutes=11
                    )
                ),
            )
        )

    def test_unknown_token_is_rejected(self):
        now = datetime(
            2026,
            8,
            13,
            15,
            0,
            0,
        )

        create_mobile_pairing_token(
            now=now,
            ttl_seconds=600,
        )

        self.assertFalse(
            consume_mobile_pairing_token(
                "not-a-real-token",
                now=(
                    now
                    + timedelta(
                        minutes=1
                    )
                ),
            )
        )

    def test_generator_stores_only_hash_not_raw_token(self):
        token = (
            create_mobile_pairing_token()
        )

        text = self.state_path.read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            token,
            text,
        )

        self.assertIn(
            "token_sha256",
            text,
        )


if __name__ == "__main__":
    unittest.main()
