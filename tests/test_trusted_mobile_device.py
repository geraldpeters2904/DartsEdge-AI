import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.services.trusted_mobile_device_service import (
    create_trusted_device,
    revoke_all_trusted_devices,
    revoke_trusted_device,
    trusted_device_count,
    valid_trusted_device,
)


class TrustedMobileDeviceTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        self.state_path = (
            Path(self.tempdir.name)
            / "trusted.json"
        )

        self.env = patch.dict(
            os.environ,
            {
                "DARTSEDGE_TRUSTED_DEVICE_STATE": (
                    str(self.state_path)
                )
            },
        )

        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tempdir.cleanup()

    def test_device_survives_service_reload(self):
        now = datetime(
            2026, 8, 13, 15, 0, 0
        )

        token = create_trusted_device(
            now=now,
            days=30,
        )

        self.assertTrue(
            self.state_path.exists()
        )

        self.assertTrue(
            valid_trusted_device(
                token,
                now=(
                    now
                    + timedelta(days=5)
                ),
            )
        )

    def test_raw_token_is_not_stored(self):
        token = create_trusted_device()

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

    def test_expired_device_is_rejected(self):
        now = datetime(
            2026, 8, 13, 15, 0, 0
        )

        token = create_trusted_device(
            now=now,
            days=1,
        )

        self.assertFalse(
            valid_trusted_device(
                token,
                now=(
                    now
                    + timedelta(days=2)
                ),
            )
        )

    def test_single_device_can_be_revoked(self):
        token = create_trusted_device()

        self.assertTrue(
            valid_trusted_device(token)
        )

        self.assertTrue(
            revoke_trusted_device(token)
        )

        self.assertFalse(
            valid_trusted_device(token)
        )

    def test_all_devices_can_be_revoked(self):
        create_trusted_device()
        create_trusted_device()

        self.assertEqual(
            trusted_device_count(),
            2,
        )

        self.assertEqual(
            revoke_all_trusted_devices(),
            2,
        )

        self.assertEqual(
            trusted_device_count(),
            0,
        )

    def test_state_is_valid_json(self):
        create_trusted_device()

        payload = json.loads(
            self.state_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertIsInstance(
            payload["devices"],
            list,
        )


if __name__ == "__main__":
    unittest.main()
