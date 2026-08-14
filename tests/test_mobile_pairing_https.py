import os
import unittest
from unittest.mock import patch

from app.services.mobile_pairing_display_service import (
    DEFAULT_HTTPS_BASE_URL,
    build_mobile_pairing_display,
    mobile_base_url,
)

class MobilePairingHttpsTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {},
        clear=True,
    )
    def test_default_base_url_is_https(self):
        self.assertEqual(
            mobile_base_url(),
            DEFAULT_HTTPS_BASE_URL,
        )
        self.assertTrue(
            mobile_base_url().startswith(
                "https://"
            )
        )

    @patch.dict(
        os.environ,
        {
            "DARTSEDGE_MOBILE_BASE_URL": (
                "https://example.ts.net/"
            )
        },
        clear=True,
    )
    def test_configured_base_url_is_used(self):
        self.assertEqual(
            mobile_base_url(),
            "https://example.ts.net",
        )

    @patch(
        "app.services."
        "mobile_pairing_display_service."
        "create_mobile_pairing_token",
        return_value="abc123",
    )
    @patch.dict(
        os.environ,
        {
            "DARTSEDGE_MOBILE_BASE_URL": (
                "https://example.ts.net"
            )
        },
        clear=True,
    )
    def test_pairing_url_uses_https_base(
        self,
        token,
    ):
        display = build_mobile_pairing_display()

        self.assertEqual(
            display.pairing_url,
            (
                "https://example.ts.net/"
                "mobile-pair/abc123"
            ),
        )
        self.assertTrue(
            display.qr_data_uri.startswith(
                "data:image/png;base64,"
            )
        )

if __name__ == "__main__":
    unittest.main()
